# Canonical A180205 build. Project owner: Carlo Corti.
CC = gcc-13
CXX = g++-13
WARN = -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wdouble-promotion -Wformat=2
CFLAGS = -std=c17 -O3 -march=native -mtune=native -flto -funroll-loops -fomit-frame-pointer -fopenmp $(WARN)
CXXFLAGS = -std=c++17 -O3 -march=native -fopenmp $(WARN)
LDLIBS = -lcrypto
.PHONY: all ie test clean
all: a180205
ie: ../check/ie
a180205: a180205.c Makefile
	$(CC) $(CFLAGS) a180205.c -o $@ $(LDLIBS)
../check/ie: ../check/ie.cpp Makefile
	$(CXX) $(CXXFLAGS) $< -o $@ $(LDLIBS)
test:
	python3 -B ../check/verify.py --build
clean:
	rm -f a180205 ../check/ie
