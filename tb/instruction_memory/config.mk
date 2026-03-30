TARGET := inst_mem_tb

SRCS := $(TEST_DIR)/inst_mem_tb.cpp \
        $(HW_ROOT)/common/Instruction/instruction.cpp

EXTRA_CXXFLAGS := -I$(HW_ROOT)/common/sram