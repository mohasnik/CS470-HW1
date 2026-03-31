TARGET := counter_tb

SRCS := $(TEST_DIR)/counter_tb.cpp

EXTRA_CXXFLAGS := -I$(HW_ROOT)/common/counter
