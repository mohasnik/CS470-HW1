TARGET := sram_inst_tb

SRCS := $(TEST_DIR)/sram_inst_tb.cpp \
        $(HW_ROOT)/common/Instruction/instruction.cpp

EXTRA_CXXFLAGS := -I$(HW_ROOT)/common/sram