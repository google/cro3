CC := gcc
CXX := g++

PLUGINS_DIR  := $(shell $(CXX) -print-file-name=plugin)

CXXFLAGS := -I${PLUGINS_DIR}/include -I${PLUGINS_DIR}/include/c-family
CXXFLAGS += -std=gnu++98 -fno-rtti -Wno-narrowing -Og
CXXFLAGS += -fPIC -shared -ggdb -Wall -W -fvisibility=hidden
CXXFLAGS += -lrt -lpthread
CXXFLAGS += -D_FORTIFY_SOURCE=2 -Wextra -Wno-unused-variable
CXXFLAGS += -Wl,-z,relro -Werror

all: cachereader roafteriniter

roafteriniter: roafteriniter.c
	@echo "[+] Building roafteriniter"
	@$(CXX) $(CXXFLAGS) -o roafteriniter.so roafteriniter.c

cachereader: cachereader.c
	gcc -o cachereader cachereader.c -lpthread -lrt

# Kernel
KCONFIG="allmodconfig"
STAGE1_ARG="-fplugin=$(shell pwd)/roafteriniter.so"
STAGE2_ARG=${STAGE1_ARG}" -fplugin-arg-roafteriniter-stage2"
kern: cachereader kern1 kern2
	@./cachereader /tmp/rai_final "/final" > /tmp/rai_rf
	@./postprocess.py --fname /tmp/rai_rf

kern1: roafteriniter
	@echo "[+] Building kernel with plugin stage1"
	@cd ${KDIR} ; \
	 make clean -j40 > /dev/null ; \
	 make ${KCONFIG} > /dev/null ; \
	 make \
		CFLAGS_MODULE=${STAGE1_ARG} \
		CFLAGS_KERNEL=${STAGE1_ARG} \
		ARCH_CFLAGS=${STAGE1_ARG} \
		-j40 > /dev/null

kern2:
	@echo "[+] Building kernel with plugin stage2"
	@cd ${KDIR} ; \
	 make clean > /dev/null ; \
	 make ${KCONFIG} > /dev/null ; \
	 make \
		CFLAGS_MODULE=${STAGE2_ARG} \
		CFLAGS_KERNEL=${STAGE2_ARG} \
		ARCH_CFLAGS=${STAGE2_ARG} \
		-j40 > /dev/null

# Testing

# cache-test
ctest: cache.h
	@echo "${MAKEPR}Testing cache implementation"
	@CPLUS_INCLUDE_PATH=${GTEST_INCDIR} \
	$(CXX) -fPIC -I${GTEST_INCDIR} -c cache_test.cc

	@$(CXX) -o ./cache_test \
		./cache_test.o \
		-L${GTEST_LIBPATH} -lgtest -lpthread -lrt
	@LD_LIBRARY_PATH=${GTEST_LIBPATH} ./cache_test

# x86_64 test
test: test1 test2

test1: clean cachereader roafteriniter
	@echo "[+] test1"
	@$(CC) -fplugin=./roafteriniter.so ./tests/test.c
	@./cachereader /tmp/rai_int "/int"

test2: cleanlock cachereader roafteriniter
	@echo "[+] test2"
	@$(CC) -fplugin=./roafteriniter.so -fplugin-arg-roafteriniter-stage2 ./tests/test.c
	@./cachereader /tmp/rai_final "/final" > /tmp/rai_rf
	@./postprocess.py --fname /tmp/rai_rf

# ARM64 test(cross compiler only)
arm64_test: arm64_test1 arm64_test2

arm64_test1: clean cachereader roafteriniter
	@echo "[+] arm64_test1"
	@aarch64-linux-gnu-gcc -fplugin=./roafteriniter.so ./tests/test.c

	@./cachereader /tmp/rai_int "/int"
arm64_test2: cleanlock cachereader roafteriniter
	@echo "[+] arm64_test2"
	@aarch64-linux-gnu-gcc -fplugin=./roafteriniter.so -fplugin-arg-roafteriniter-stage2 ./tests/test.c
	@./cachereader /tmp/rai_final "/final" > /tmp/rai_rf
	@./postprocess.py --fname /tmp/rai_rf

cleanlock:
	rm -rf /dev/shm/sem.chk /dev/shm/sem.final /dev/shm/sem.int

clean: cleanlock
	rm -f *.so a.out /tmp/rai_* *.o cachereader cache_test
