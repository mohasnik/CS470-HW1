TARGET := sram_tb

SRCS := $(TEST_DIR)/sram_tb.cpp

EXTRA_CXXFLAGS := -I$(HW_ROOT)/common/sram
