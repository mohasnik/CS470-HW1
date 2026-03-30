# ── Shared configuration ──────────────────────────────────────────────────────

SYSTEMC_HOME ?= /Users/mohasnik/systemc
SYSTEMC_INC  := $(SYSTEMC_HOME)/include
SYSTEMC_LIB  := $(SYSTEMC_HOME)/lib

HW_ROOT := ../hw
BUILD   := ../build/$(TEST_DIR)

CXX      := g++
CXXFLAGS := -std=c++17 -Wall \
            -I$(SYSTEMC_INC) \
            -I$(HW_ROOT)/common/Instruction \
            -I$(HW_ROOT)/common/instruction_memory \
            -DPROJECT_SOURCE_DIR='"$(abspath ..)"' \
            -MMD -MP
LDFLAGS  := -L$(SYSTEMC_LIB) -lsystemc -Wl,-rpath,$(SYSTEMC_LIB)

DEPS := $(patsubst %.cpp,$(BUILD)/%.d,$(notdir $(SRCS)))

# ── Test selection ────────────────────────────────────────────────────────────

ifndef TEST_DIR
$(error TEST_DIR is not set. Usage: make TEST_DIR=<test_name>  e.g. TEST_DIR=instruction_memory)
endif

# Pull in test-specific variables: TARGET, SRCS, and optionally EXTRA_CXXFLAGS
include $(TEST_DIR)/config.mk

CXXFLAGS += $(EXTRA_CXXFLAGS)
TARGET_BIN := $(BUILD)/$(TARGET)

# ── Rules ─────────────────────────────────────────────────────────────────────

.PHONY: all run clean

all: $(TARGET_BIN)

-include $(DEPS)

$(TARGET_BIN): $(SRCS) | $(BUILD)
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS) -MF $(BUILD)/$(notdir $<).d

$(BUILD):
	mkdir -p $(BUILD)

run: all
	cd $(BUILD) && ./$(TARGET)

clean:
	rm -rf $(BUILD)