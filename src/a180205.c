/* A180205: permutations of 0..n-1 representable as consecutive adjacent
 * sums of a sequence of n+1 nonnegative integers.
 * Project owner: Carlo Corti. Maintainer: Luna / OpenAI Codex.
 * Historical reference terms 1..17: R. H. Hardin. No license inferred.
 * C17 + unsigned __int128, POSIX/Linux, OpenMP, OpenSSL 3.
 * Build: make -C src. Specification: outputs/strat0/basis.md.
 * Weighted pull DP, parity-packed rows, colex ranks, two resident W layers.
 * COMPLETE is native coverage, never independent scientific admission.
 * See validation/ and outputs/dev0/ for the separate validation boundary.
 */
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <omp.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>

__extension__ typedef unsigned __int128 U;
_Static_assert(sizeof(U)==16 && sizeof(off_t)>=8 && sizeof(size_t)>=8,
               "64-bit host and 128-bit scalar required");
#define CAP 30U
#define QMAX UINT64_C(262144)
#define REC 1024U
#define GIB UINT64_C(1073741824)
static uint64_t C[31][31], off[31];
static U fact[31];
static unsigned M,w;
static int dirfd=-1;
static volatile sig_atomic_t stopped;
static double started,heartbeat;
static const char *root;
static uint64_t qrows=QMAX;
static unsigned threads=8;
static unsigned seconds=3000;
static unsigned char config_hash[32];
static uint64_t booked_start,session_reads;
static bool compute_started;
typedef struct {uint64_t seq,phase,h,rank,n,cursor,reads,millis,workers,quantum;U sum,result[31];} State;
static State telemetry;
static bool telemetry_valid,audit_active;
static void progress(const State *s,const char *reason);
static void io_heartbeat(void);

static void die(const char *s) { fprintf(stderr,"ERROR: %s (%s)\n",s,strerror(errno)); exit(1); }
static void need(bool ok,const char *s) { if(!ok) { errno=EINVAL; die(s); } }
static double now(void) { struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) die("clock"); return (double)t.tv_sec+(double)t.tv_nsec*1e-9; }
static void sigstop(int s) { (void)s; stopped=1; }
static U add(U a,U b) { need(a<=~(U)0-b,"128-bit addition overflow"); return a+b; }
static U mul(U a,U b) { need(!b || a<=~(U)0/b,"128-bit multiplication overflow"); return a*b; }
static void dec(U a,char s[40]) { char t[40]; unsigned i=0,j=0; do {t[i++]=(char)('0'+a%10);a/=10;}while(a); while(i) s[j++]=t[--i];s[j]=0; }
static uint64_t number(const char *s,uint64_t lo,uint64_t hi) {
    uint64_t a=0; need(*s!=0,"empty number");
    for(;*s;s++) { need(*s>='0'&&*s<='9',"unsigned decimal grammar"); unsigned v=(unsigned)(*s-'0'); need(a<=(hi-v)/10 && v<=hi,"number range"); a=a*10+v; }
    need(a>=lo && a<=hi,"number range");return a;
}
static void init(unsigned n) {
    need(n>=1 && n<=CAP,"maximum index 1..30");M=n-1;w=M/2+1;
    for(unsigned i=0;i<=30;i++) { C[i][0]=1;C[i][i]=1;for(unsigned j=1;j<i;j++) C[i][j]=C[i-1][j-1]+C[i-1][j]; }
    off[0]=0; for(unsigned h=1;h<=M+1;h++) off[h]=off[h-1]+C[M][h-1];
    fact[0]=1;for(unsigned i=1;i<=30;i++) fact[i]=mul(fact[i-1],i);
}
static uint32_t unrank(uint64_t rank,unsigned h) {
    uint32_t mask=0;unsigned b=M;
    for(unsigned i=h;i;i--) {do {need(b>0,"unrank");--b;}while(C[b][i]>rank);mask|=UINT32_C(1)<<b;rank-=C[b][i];}
    need(rank==0,"unrank residue");return mask;
}
static uint32_t nextmask(uint32_t a) { uint32_t low=a&(~a+1U),b=a+low;return b|(((a^b)>>2)/low); }
static uint64_t findex(uint32_t a) {unsigned h=0;uint64_t r=0;while(a) {unsigned b=(unsigned)__builtin_ctz(a);r+=C[b][++h];a&=a-1;}return off[h]+r;}
static void put64(unsigned char *p,uint64_t a) {for(unsigned i=0;i<8;i++){p[i]=(unsigned char)a;a>>=8;}}
static uint64_t get64(const unsigned char *p) {uint64_t a=0;for(unsigned i=8;i;i--) a=(a<<8)|p[i-1];return a;}
static void put128(unsigned char *p,U a) {put64(p,(uint64_t)a);put64(p+8,(uint64_t)(a>>64));}
static U get128(const unsigned char *p) {return (U)get64(p)|((U)get64(p+8)<<64);}
static void hash(const void *p,size_t n,unsigned char out[32]) {unsigned len=0;need(EVP_Digest(p,n,out,&len,EVP_sha256(),NULL)==1&&len==32,"SHA256");}
static int openfile(const char *name,int flags) {int fd=openat(dirfd,name,flags|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0)die(name);struct stat st;if(fstat(fd,&st))die("stat");need(S_ISREG(st.st_mode),"regular file required");return fd;}
static void io(int fd,void *data,size_t len,uint64_t pos,bool writing) {
    unsigned char *p=data;need(pos<=INT64_MAX && len<=(uint64_t)INT64_MAX-pos,"file offset");
    while(len) {ssize_t z=writing?pwrite(fd,p,len,(off_t)pos):pread(fd,p,len,(off_t)pos);if(z<0&&errno==EINTR)continue;if(z<=0)die("short I/O");p+=(size_t)z;len-=(size_t)z;pos+=(uint64_t)z;io_heartbeat();}
}
static void syncfd(int fd) {if(fsync(fd))die("fsync");}
static void closefd(int fd) {if(close(fd))die("close");}
static uint64_t fsize(int fd) {struct stat st;if(fstat(fd,&st))die("fstat");need(st.st_size>=0,"negative size");return (uint64_t)st.st_size;}
static void digest_file(int fd,uint64_t pos,uint64_t len,unsigned char out[32]) {
    unsigned char buf[65536];EVP_MD_CTX *ctx=EVP_MD_CTX_new();need(ctx!=NULL,"digest allocation");need(EVP_DigestInit_ex(ctx,EVP_sha256(),NULL)==1,"digest init");
    while(len) {size_t n=len>sizeof buf?sizeof buf:(size_t)len;io(fd,buf,n,pos,false);need(EVP_DigestUpdate(ctx,buf,n)==1,"digest update");pos+=n;len-=n;}
    unsigned z=0;need(EVP_DigestFinal_ex(ctx,out,&z)==1&&z==32,"digest final");EVP_MD_CTX_free(ctx);
}
static void hashpath(const char *p,unsigned char out[32]) {int fd=open(p,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)die(p);digest_file(fd,0,fsize(fd),out);closefd(fd);}
static void hex(const unsigned char a[32],char s[65]) {static const char d[]="0123456789abcdef";for(unsigned i=0;i<32;i++){s[2*i]=d[a[i]>>4];s[2*i+1]=d[a[i]&15];}s[64]=0;}
static void atomic_file(const char *tmp,const char *dst,const void *p,size_t len,bool replace) {
    int fd=openfile(tmp,O_WRONLY|O_CREAT|O_TRUNC);io(fd,(void *)p,len,0,true);syncfd(fd);closefd(fd);
    if(replace) {if(renameat(dirfd,tmp,dirfd,dst))die("rename");}
    else {if(linkat(dirfd,tmp,dirfd,dst,0))die("no-clobber link");if(unlinkat(dirfd,tmp,0))die("temporary unlink");}
    syncfd(dirfd);
}
static void write_new(const char *name,const void *p,size_t n) {int fd=openfile(name,O_WRONLY|O_CREAT|O_EXCL);io(fd,(void *)p,n,0,true);syncfd(fd);closefd(fd);syncfd(dirfd);}

/* Only the final 32 bytes are the record digest. Unused bytes must be zero.
 * State: seq, phase(0 DP,1 convolution,2 complete),h,rank,n,cursor,reads,
 * sum, results[1..30]. Descriptor: completed DP h/start/count and digests.
 * Every record binds its predecessor, exact config and binary/source/build.
 */
static void encode(const State *s,unsigned char r[REC]) {
    memset(r,0,REC);memcpy(r,"A180205\0",8);put64(r+8,s->seq);put64(r+16,s->phase);put64(r+24,s->h);put64(r+32,s->rank);put64(r+40,s->n);put64(r+48,s->cursor);put64(r+56,s->reads);put128(r+64,s->sum);
    for(unsigned i=1;i<=30;i++) put128(r+80+16*(i-1),s->result[i]);
    memcpy(r+560,config_hash,32);
    put64(r+712,s->millis);
    put64(r+720,s->workers);put64(r+728,s->quantum);
}
static State decode(const unsigned char r[REC]) {
    State s={0};need(memcmp(r,"A180205\0",8)==0 && memcmp(r+560,config_hash,32)==0,"record identity");
    unsigned char d[32];hash(r,REC-32,d);need(!memcmp(d,r+REC-32,32),"record digest");
    s.seq=get64(r+8);s.phase=get64(r+16);s.h=get64(r+24);s.rank=get64(r+32);s.n=get64(r+40);s.cursor=get64(r+48);s.reads=get64(r+56);s.sum=get128(r+64);
    for(unsigned i=1;i<=30;i++) {s.result[i]=get128(r+80+16*(i-1));need(s.result[i]<=fact[i],"result bound");}
    s.millis=get64(r+712);
    s.workers=get64(r+720);s.quantum=get64(r+728);
    uint64_t maxreads=M>=3?(UINT64_C(1)<<(M-3))*M*(M+3):(M==2?5:M);
    need(s.reads<=maxreads,"read counter domain");
    need(s.workers>=1 && s.workers<=16 && s.quantum>=1 && s.quantum<=QMAX,"scheduling record domain");
    for(unsigned i=736;i<REC-32;i++)need(r[i]==0,"reserved record bytes");
    need(s.phase<=2 && s.h>=1 && s.h<=M+1,"phase/layer domain");
    need(s.n>=1 && s.n<=M+2,"convolution index domain");
    if(s.phase==0) need(s.h<=M && s.rank<C[M][s.h] && s.n==1 && s.cursor==0 && s.sum==0,"DP frontier");
    else {need(s.h==M+1 && s.rank==0,"complete DP frontier");if(s.phase==1) {need(s.n<=M+1,"convolution phase");uint64_t lim=s.n==1?1:UINT64_C(1)<<(s.n-2);need(s.cursor<lim && s.sum<=fact[s.n],"convolution frontier");}else need(s.n==M+2 && s.cursor==0 && s.sum==0,"terminal frontier");}
    for(unsigned i=(unsigned)s.n;i<=30;i++)need(s.result[i]==0,"future result");
    return s;
}
static void layername(unsigned h,char name[9]) {int z=snprintf(name,9,"lay%u.bin",h%3);need(z==8,"layer name");}
static void cells_io(int fd,U *a,uint64_t start,uint64_t count,bool writing) {
    unsigned char b[65536];uint64_t i=0;
    while(i<count) {uint64_t n=count-i;if(n>sizeof b/16)n=sizeof b/16;
        if(writing)for(uint64_t j=0;j<n;j++)put128(b+16*j,a[i+j]);
        io(fd,b,(size_t)(n*16),(start+i)*16,writing);
        if(!writing)for(uint64_t j=0;j<n;j++)a[i+j]=get128(b+16*j);
        i+=n;
    }
}
static uint64_t arrays(void) {uint64_t peak=0;for(unsigned h=1;h<=M;h++){uint64_t n=(C[M][h-1]+C[M][h])*w*16;if(n>peak)peak=n;}return peak+(UINT64_C(1)<<M)*16;}
static void progress(const State *s,const char *reason) {
    fprintf(stderr,"max=%u phase=%"PRIu64" layer=%"PRIu64" committed_rank=%"PRIu64" index=%"PRIu64" cursor=%"PRIu64" complete_terms=%"PRIu64" session_s=%.0f limit_s=%u committed_ms=%"PRIu64" session_reads=%"PRIu64" total_reads=%"PRIu64" array_bound_bytes=%"PRIu64" requested_workers=%u committed_workers=%"PRIu64" quantum=%"PRIu64" stop=%s\n",M+1,s->phase,s->h,s->rank,s->n,s->cursor,s->n-1,now()-started,seconds,s->millis,compute_started?s->reads-session_reads:0,s->reads,arrays(),threads,s->workers,s->quantum,reason);heartbeat=now();
}
static void io_heartbeat(void) {
    if(now()-heartbeat<5)return;
    if(audit_active){fprintf(stderr,"max=%u phase=AUDIT stop=AUDIT_UNVERIFIED session_s=%.0f\n",M+1,now()-started);heartbeat=now();}
    else if(telemetry_valid)progress(&telemetry,"IO_COMMITTED_FRONTIER");
}
static uint64_t available(void) {FILE *f=fopen("/proc/meminfo","r");if(!f)die("meminfo");char line[256];uint64_t a=0;while(fgets(line,sizeof line,f)) {unsigned long long k;if(sscanf(line,"MemAvailable: %llu kB",&k)==1)a=(uint64_t)k*1024;}if(fclose(f))die("meminfo close");need(a>0,"MemAvailable missing");return a;}
static void resources(void) {uint64_t a=arrays()+GIB/4;need(a<=48*GIB,"allocation48GiB");need(available()>=a+4*GIB,"MemAvailable headroom");struct statvfs st;if(fstatvfs(dirfd,&st))die("statvfs");uint64_t disk=arrays()*2+GIB/4;need(disk<=96*GIB,"disk96GiB");need((U)st.f_bavail*st.f_frsize>=disk,"free disk reserve");}
static U *allocate(uint64_t cells) {need(cells<=SIZE_MAX/16,"allocation size");U *p=NULL;int e=posix_memalign((void **)&p,64,(size_t)(cells*16));if(e){errno=e;die("allocate");}return p;}

/* Exclusive output-row ownership; previous layer and C are read-only.
 * Deleted-bit ranks are prefix+suffix binomial sums computed once per row.
 */
static uint64_t rows(U *cur,const U *prev,U *F,unsigned h,uint64_t lo,uint64_t hi) {
    uint64_t reads=0;
    #pragma omp parallel num_threads(threads) reduction(+:reads)
    {
        uint64_t t=(uint64_t)omp_get_thread_num(),nt=(uint64_t)omp_get_num_threads();
        uint64_t a=lo+(hi-lo)*t/nt,b=lo+(hi-lo)*(t+1)/nt;
        uint32_t mask=a<b?unrank(a,h):0;
        for(uint64_t r=a;r<b;r++) {
            unsigned bit[30],i=0,parity=0;uint32_t x=mask;
            while(x){bit[i++]=(unsigned)__builtin_ctz(x);parity^=(bit[i-1]+1)&1U;x&=x-1;}
            uint64_t prefix[31]={0},suffix[31]={0};
            for(i=0;i<h;i++)prefix[i+1]=prefix[i]+C[bit[i]][i+1];
            for(i=h;i;i--)suffix[i-1]=suffix[i]+C[bit[i-1]][i-1];
            U *out=cur+r*w;memset(out,0,w*16);
            for(i=0;i<h;i++){unsigned v=bit[i]+1;uint64_t pr=prefix[i]+suffix[i+1];need(pr<C[M][h-1],"predecessor rank");
                for(unsigned s=parity;s<=v;s+=2){unsigned j=(v-s)/2;out[s/2]=add(out[s/2],prev[pr*w+j]);++reads;}
            }
            U sum=0;for(i=0;i<w;i++)sum=add(sum,out[i]);need(sum>=1&&sum<=fact[h],"tail count bound");F[off[h]+r]=sum;
            if(r+1<b)mask=nextmask(mask);
        }
    }
    return reads;
}
static uint64_t compute_quantum(U *cur,const U *prev,U *F,unsigned h,uint64_t lo,uint64_t hi) {
    uint64_t reads=0;
    /* Internal service slices do not move the durable recovery frontier. */
    for(uint64_t r=lo;r<hi;){uint64_t end=r+4096;if(end>hi)end=hi;
        reads+=rows(cur,prev,F,h,r,end);r=end;
        if(telemetry_valid && now()-heartbeat>=5)progress(&telemetry,"COMPUTE_UNCOMMITTED");
    }
    return reads;
}
static void commit(State *s,unsigned char last[REC],unsigned rh,uint64_t lo,uint64_t count,U *cur,U *F) {
    need(s->seq<262144,"journal record ceiling");
    double elapsed_ms=(now()-started)*1000;
    need(elapsed_ms>=0 && elapsed_ms<1e15,"session clock domain");
    uint64_t delta_ms=(uint64_t)elapsed_ms;
    need(booked_start<=UINT64_MAX-delta_ms,"booked clock overflow");
    s->millis=booked_start+delta_ms;
    s->workers=threads;s->quantum=qrows;
    unsigned char r[REC];++s->seq;encode(s,r);memcpy(r+592,last+(REC-32),32);put64(r+624,rh);put64(r+632,lo);put64(r+640,count);
    if(count) {
        char name[9];layername(rh,name);int fd=openfile(name,O_RDWR|O_CREAT);
        cells_io(fd,cur+lo*w,lo*w,count*w,true);syncfd(fd);digest_file(fd,lo*w*16,count*w*16,r+648);closefd(fd);
        fd=openfile("f.bin",O_RDWR);cells_io(fd,F+off[rh]+lo,off[rh]+lo,count,true);syncfd(fd);digest_file(fd,(off[rh]+lo)*16,count*16,r+680);closefd(fd);
    }
    hash(r,REC-32,r+REC-32);int fd=openfile("evt.bin",O_RDWR|O_CREAT);io(fd,r,REC,(s->seq-1)*REC,true);syncfd(fd);closefd(fd);
    atomic_file("ctl.tmp","ctl.bin",r,REC,true);memcpy(last,r,REC);
    telemetry=*s;telemetry_valid=true;
}
static void values(int fd,uint64_t start,uint64_t count,unsigned h,bool row) {
    U buf[4096];uint64_t step=row?w:1;
    for(uint64_t i=0;i<count;) {
        uint64_t n=count-i,cap=(4096/step)*step;if(n>cap)n=cap;
        cells_io(fd,buf,start+i,n,false);
        for(uint64_t k=0;k<n;k+=step){U sum=0;for(uint64_t j=0;j<step;j++){need(buf[k+j]<=fact[h],"state value bound");sum=add(sum,buf[k+j]);}need(sum>=1&&sum<=fact[h],"row/tail semantic bound");}
        i+=n;
    }
}
static void row_relation(int wf,int ff,unsigned h,uint64_t lo,uint64_t count) {
    U wb[4096],fb[4096];uint64_t done=0;
    uint32_t mask=unrank(lo,h);
    while(done<count){uint64_t nr=count-done;if(nr>4096/w)nr=4096/w;
        cells_io(wf,wb,(lo+done)*w,nr*w,false);cells_io(ff,fb,off[h]+lo+done,nr,false);
        for(uint64_t r=0;r<nr;r++) {unsigned parity=0;for(uint32_t x=mask;x;x&=x-1)parity^=((unsigned)__builtin_ctz(x)+1)&1U;
            U sum=0;for(unsigned j=0;j<w;j++){U x=wb[r*w+j];need(x<=fact[h],"W cell bound");need(parity+2*j<=M || x==0,"W padding");sum=add(sum,x);}need(sum==fb[r],"W/F semantic equality");
            if(done+r+1<count)mask=nextmask(mask);
        }done+=nr;
    }
}
static State audit(unsigned char last[REC]) {
    audit_active=true;
    int fd=openfile("ctl.bin",O_RDONLY);need(fsize(fd)==REC,"control length");io(fd,last,REC,0,false);closefd(fd);State end=decode(last);
    telemetry=end;telemetry_valid=true;
    int jf=openfile("evt.bin",O_RDONLY);need(end.seq>=1&&end.seq<=262144&&fsize(jf)>=end.seq*REC,"journal length");
    unsigned char prevhash[32]={0},r[REC],d[32];uint64_t dh=1,dr=0;State prev={0};
    for(uint64_t z=0;z<end.seq;z++) {
        io(jf,r,REC,z*REC,false);State s=decode(r);need(s.seq==z+1&&!memcmp(r+592,prevhash,32),"journal chain");
        uint64_t h=get64(r+624),lo=get64(r+632),count=get64(r+640);
        if(!count)for(unsigned i=648;i<712;i++)need(r[i]==0,"unused span digests");
        if(z==0)need(h==0 && lo==0 && count==0 && s.reads==0 && s.n==1 && s.cursor==0 && s.h==1 && s.rank==0 && s.sum==0 && s.phase==(M==0?1U:0U),"initial record");
        else if(count) {
            need(h==dh && lo==dr && h<=M && count<=s.quantum && count<=C[M][h]-lo,"span frontier");dr+=count;if(dr==C[M][h]){++dh;dr=0;}
            need(s.h==dh && s.rank==dr && s.phase==(dh>M?1U:0U) && s.n==1 && s.cursor==0,"span end state");
            int f=openfile("f.bin",O_RDONLY);digest_file(f,(off[h]+lo)*16,count*16,d);need(!memcmp(d,r+680,32),"committed F digest");values(f,off[h]+lo,count,(unsigned)h,false);closefd(f);
            if(h+1>=end.h) {char name[9];layername((unsigned)h,name);f=openfile(name,O_RDONLY);digest_file(f,lo*w*16,count*w*16,d);need(!memcmp(d,r+648,32),"committed W digest");int ff=openfile("f.bin",O_RDONLY);row_relation(f,ff,(unsigned)h,lo,count);closefd(ff);closefd(f);}
            need(s.reads>=prev.reads,"work monotonicity");
        } else if(z) {
            need(h==0 && lo==0,"convolution descriptor");
            need(prev.phase==1 && s.phase>=1 && s.h==prev.h && s.rank==0 && s.reads==prev.reads,"convolution transition");
            uint64_t limit=prev.n==1?1:UINT64_C(1)<<(prev.n-2);
            if(s.n==prev.n)need(s.cursor>prev.cursor && s.cursor-prev.cursor<=s.quantum && s.cursor<limit && s.sum>=prev.sum,"convolution partial");
            else {need(s.n==prev.n+1 && s.cursor==0 && s.sum==0 && s.result[prev.n]>=prev.sum,"convolution completion");}
            for(unsigned k=1;k<prev.n;k++)need(s.result[k]==prev.result[k],"result preservation");
        }
        need(s.millis>=prev.millis,"committed time monotonicity");
        if(now()-heartbeat>=5)progress(&s,"AUDITING");
        memcpy(prevhash,r+REC-32,32);prev=s;
    }
    need(!memcmp(r,last,REC),"control/journal equality");closefd(jf);
    int f=openfile("f.bin",O_RDONLY);U one;cells_io(f,&one,0,1,false);need(one==1,"empty F");closefd(f);
    audit_active=false;return end;
}
static void journal_room(const State *s) {
    uint64_t records=s->seq;
    if(s->phase==0)for(unsigned h=(unsigned)s->h;h<=M;h++){uint64_t remain=C[M][h]-(h==s->h?s->rank:0);records+=(remain+qrows-1)/qrows;}
    if(s->phase<2)for(unsigned n=(unsigned)s->n;n<=M+1;n++){uint64_t limit=n==1?1:UINT64_C(1)<<(n-2);uint64_t remain=limit-(s->phase==1&&n==s->n?s->cursor:0);records+=(remain+qrows-1)/qrows;}
    need(records<=262144,"quantum too small for remaining journal capacity");
}
static void configuration(unsigned n,bool fresh) {
    char exe[PATH_MAX],source[PATH_MAX],build[PATH_MAX],base[PATH_MAX];ssize_t k=readlink("/proc/self/exe",exe,sizeof exe-1);need(k>0&&(size_t)k<sizeof exe-1,"executable path");exe[k]=0;char parent[PATH_MAX];memcpy(parent,exe,(size_t)k+1);char *slash=strrchr(parent,'/');need(slash!=NULL,"exe directory");*slash=0;
    need(snprintf(source,sizeof source,"%s/a180205.c",parent)<(int)sizeof source,"source path");need(snprintf(build,sizeof build,"%s/Makefile",parent)<(int)sizeof build,"build path");need(snprintf(base,sizeof base,"%s/../data/b180205.txt",parent)<(int)sizeof base,"base path");
    unsigned char hs[32],hb[32],he[32],hd[32];char ss[65],bs[65],es[65],ds[65];hashpath(source,hs);hashpath(build,hb);hashpath(exe,he);
    if(fresh){int f=open(base,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(f<0)die("baseline");uint64_t z=fsize(f);need(z<65536,"baseline size");char b[65536];io(f,b,(size_t)z,0,false);closefd(f);
        size_t used=0;unsigned lines=0;while(used<(size_t)z && lines<17){if(b[used++]=='\n')++lines;}
        need(lines==17,"historical prefix missing");b[used++]='\n';write_new("base.txt",b,used);
    }
    int f=openfile("base.txt",O_RDONLY);digest_file(f,0,fsize(f),hd);closefd(f);hex(hs,ss);hex(hb,bs);hex(he,es);hex(hd,ds);
    need(!strcmp(ds,"466a29c52f24b11359586313c1abe2f30c87be213189a54fe3f1292520bc1e07"),"frozen known prefix identity");
    char cfg[1024];int len=snprintf(cfg,sizeof cfg,"{\"sequence\":\"A180205\",\"schema\":1,\"maximum\":%u,\"source\":\"%s\",\"makefile\":\"%s\",\"executable\":\"%s\",\"base\":\"%s\",\"encoding\":\"u128le-colex-parity\"}\n",n,ss,bs,es,ds);need(len>0&&(size_t)len<sizeof cfg,"config length");hash(cfg,(size_t)len,config_hash);
    if(fresh)write_new("cfg.json",cfg,(size_t)len);
    else {char stored[1024];f=openfile("cfg.json",O_RDONLY);need(fsize(f)==(uint64_t)len,"config length mismatch");io(f,stored,(size_t)len,0,false);closefd(f);need(!memcmp(cfg,stored,(size_t)len),"source/build/bin/config mismatch");}
}
static void finish(const State *s,bool check) {
    char text[2048],val[40];size_t used=0;for(unsigned n=1;n<=M+1;n++){dec(s->result[n],val);int z=snprintf(text+used,sizeof text-used,"%u %s\n",n,val);need(z>0&&(size_t)z<sizeof text-used,"result length");used+=(size_t)z;}
    unsigned char d[32];char hs[65];hash(text,used,d);hex(d,hs);char receipt[256];int z=snprintf(receipt,sizeof receipt,"{\"status\":\"COMPLETE_NATIVE_VALIDATION_PENDING\",\"maximum\":%u,\"count_sha256\":\"%s\"}\n",M+1,hs);need(z>0&&(size_t)z<sizeof receipt,"receipt length");
    const char *names[2]={"cnt.tsv","end.json"};const void *data[2]={text,receipt};size_t lens[2]={used,(size_t)z};const char *tmp[2]={"cnt.tmp","end.tmp"};
    for(unsigned i=0;i<2;i++) {struct stat st;if(fstatat(dirfd,names[i],&st,AT_SYMLINK_NOFOLLOW)==0){char b[2048];int f=openfile(names[i],O_RDONLY);need(fsize(f)==lens[i],"terminal artifact size");io(f,b,lens[i],0,false);need(!memcmp(b,data[i],lens[i]),"terminal artifact mismatch");closefd(f);}else {need(errno==ENOENT,"terminal stat");need(!check,"missing completion artifact");atomic_file(tmp[i],names[i],data[i],lens[i],false);}}
}
static void run(bool fresh,bool check) {
    unsigned char last[REC]={0};State s={0};
    if(!check)resources();
    fprintf(stderr,"max=%u phase=STARTUP root=%s mode=%s\n",M+1,root,check?"READ_ONLY":"RUN");
    if(fresh){s.h=1;s.n=1;if(M==0)s.phase=1;U one=1;int f=openfile("f.bin",O_RDWR|O_CREAT|O_EXCL);cells_io(f,&one,0,1,true);syncfd(f);closefd(f);commit(&s,last,0,0,0,NULL,NULL);}
    else s=audit(last);
    booked_start=fresh?0:s.millis;session_reads=s.reads;
    compute_started=true;
    if(s.phase<2){struct stat st;need(fstatat(dirfd,"end.json",&st,AT_SYMLINK_NOFOLLOW)!=0&&errno==ENOENT,"completion receipt with incomplete control");need(fstatat(dirfd,"cnt.tsv",&st,AT_SYMLINK_NOFOLLOW)!=0&&errno==ENOENT,"complete counts with incomplete control");}
    progress(&s,check?"READ_ONLY":"START");if(check){if(s.phase==2)finish(&s,true);return;}
    if(s.phase==2){finish(&s,false);progress(&s,"ALREADY_COMPLETE");return;}
    journal_room(&s);
    U *F=allocate(UINT64_C(1)<<M);int fd=openfile("f.bin",O_RDONLY);uint64_t frows=s.phase==0?off[s.h]+s.rank:UINT64_C(1)<<M;cells_io(fd,F,0,frows,false);closefd(fd);
    U *prev=NULL,*cur=NULL;
    if(s.phase==0){prev=allocate(C[M][s.h-1]*w);if(s.h==1){memset(prev,0,w*16);prev[0]=1;}else {char name[9];layername((unsigned)s.h-1,name);fd=openfile(name,O_RDONLY);cells_io(fd,prev,0,C[M][s.h-1]*w,false);closefd(fd);}cur=allocate(C[M][s.h]*w);
        if(s.rank){char name[9];layername((unsigned)s.h,name);fd=openfile(name,O_RDONLY);cells_io(fd,cur,0,s.rank*w,false);closefd(fd);}
    }
    while(s.phase<2 && !stopped && now()-started<(double)seconds) {
        if(s.phase==0){unsigned h=(unsigned)s.h;uint64_t lo=s.rank,hi=lo+qrows;if(hi>C[M][h])hi=C[M][h];s.reads+=compute_quantum(cur,prev,F,h,lo,hi);s.rank=hi;
            if(hi==C[M][h]){s.rank=0;++s.h;if(s.h>M)s.phase=1;}
            commit(&s,last,h,lo,hi-lo,cur,F);
            if(s.h!=h){free(prev);prev=cur;cur=NULL;if(s.phase==0)cur=allocate(C[M][s.h]*w);}
        }else {unsigned n=(unsigned)s.n;uint64_t limit=n==1?1:UINT64_C(1)<<(n-2),hi=s.cursor+qrows;if(hi>limit)hi=limit;
            if(n==1)s.sum=1;
            else {uint32_t full=(UINT32_C(1)<<(n-1))-1;U part=0,partial[16]={0};
                #pragma omp parallel num_threads(threads)
                {
                    U subtotal=0;
                    #pragma omp for schedule(static)
                    for(uint64_t a=s.cursor;a<hi;a++){U x=mul(F[findex((uint32_t)a)],F[findex(full^(uint32_t)a)]);need(x<=fact[n-1],"complement product");subtotal=add(subtotal,x);}
                    partial[omp_get_thread_num()]=subtotal;
                }
                for(unsigned t=0;t<threads;t++)part=add(part,partial[t]);
                s.sum=add(s.sum,mul(part,2));need(s.sum<=fact[n],"final bound");}
            s.cursor=hi;if(hi==limit){s.result[n]=s.sum;s.sum=0;s.cursor=0;++s.n;if(s.n==M+2)s.phase=2;}
            commit(&s,last,0,0,0,NULL,NULL);
        }
        if(now()-heartbeat>=5)progress(&s,"ACTIVE");
    }
    free(cur);free(prev);free(F);
    if(s.phase==2){finish(&s,false);progress(&s,"COMPLETE_NATIVE_VALIDATION_PENDING");}else {progress(&s,stopped?"SIGNAL_INCOMPLETE":"TIME_INCOMPLETE");exit(2);}
}
static void selftest(void) {
    init(30);need(arrays()==UINT64_C(45818139392),"array formula30");
    unsigned char b[16];U x=fact[30];put128(b,x);need(get128(b)==x,"128 serialization");
    for(unsigned h=1;h<=M;h++){uint64_t rr[3]={0,C[M][h]/2,C[M][h]-1};for(unsigned j=0;j<3;j++){uint32_t a=unrank(rr[j],h);need(findex(a)==off[h]+rr[j],"colex endpoints");}}
    char s[40];dec(x,s);need(!strcmp(s,"265252859812191058636308480000000"),"factorial30 decimal");puts("SELFTEST PASS capacity30 encoding/colex/numeric; no term computed");
}
static void usage(void) {fprintf(stderr,"a180205 run --root DIR --max N [--threads 1..16] [--seconds 1..3000] [--quantum 1..262144] [--resume]\na180205 check --root DIR --max N\na180205 selftest\nExit:0 success/read-only;2 incomplete;1 error. COMPLETE needs independent validation.\n");}
int main(int argc,char **argv) {
    started=heartbeat=now();if(argc==2 && !strcmp(argv[1],"selftest")){selftest();return 0;}
    if(argc<2){usage();return 1;}bool check=!strcmp(argv[1],"check"),fresh=true;need(check||!strcmp(argv[1],"run"),"run/check mode");unsigned n=0,seen=0;
    for(int i=2;i<argc;i++){unsigned bit=0;if(!strcmp(argv[i],"--resume")){bit=32;need(!check,"check/resume");fresh=false;}
        else {need(i+1<argc,"missing option value");const char *key=argv[i++],*v=argv[i];if(!strcmp(key,"--root")){bit=1;root=v;need(*v!=0,"empty root");}else if(!strcmp(key,"--max")){bit=2;n=(unsigned)number(v,1,30);}else if(!strcmp(key,"--threads")){bit=4;need(!check,"check/threads");threads=(unsigned)number(v,1,16);}else if(!strcmp(key,"--seconds")){bit=8;need(!check,"check/seconds");seconds=(unsigned)number(v,1,3000);}else if(!strcmp(key,"--quantum")){bit=16;need(!check,"check/quantum");qrows=number(v,1,QMAX);}else die("unknown option");}
        need(!(seen&bit),"duplicate option");seen|=bit;
    }
    need((seen&3)==3,"root and maximum required");init(n);if(check)fresh=false;
    if(fresh){if(mkdir(root,0700))die("new root (no clobber)");}
    dirfd=open(root,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(dirfd<0)die("root directory");
    int lock=openfile("lock",check?O_RDONLY:O_RDWR|O_CREAT);if(flock(lock,check?LOCK_SH|LOCK_NB:LOCK_EX|LOCK_NB))die("job locked");
    configuration(n,fresh);struct sigaction sa;memset(&sa,0,sizeof sa);sa.sa_handler=sigstop;sigemptyset(&sa.sa_mask);if(sigaction(SIGINT,&sa,NULL)||sigaction(SIGTERM,&sa,NULL))die("signal handler");
    run(fresh,check);closefd(lock);closefd(dirfd);return 0;
}
