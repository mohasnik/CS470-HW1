#!/usr/bin/env python3
import argparse
import json

RED = '\x1b[31m'
GREEN = '\x1b[32m'
RESET = '\x1b[0m'


parser = argparse.ArgumentParser()

parser.add_argument("input", help="The input JSON for comparison.", type=argparse.FileType("r"))
parser.add_argument("--reference", "-r", required=True, help="The reference JSON.", type=argparse.FileType("r"))

args = parser.parse_args()

INPUT = json.load(args.input)
REFERENCE = json.load(args.reference)

# INPUT is [{"ActiveList": [], "BusyBitTable": [bool], "DecodedPCs": int, "Exception": bool, "ExceptionPC": int, "FreeList": [int], "IntegerQueue": [{}], "PC": int, "PhysicalRegisterFile": [int], "RegisterMapTable": [int], }]
# ActiveList: [{"Done": bool, "Exception": bool, "LogicalDestination": int, "OldDestination": int, "PC": int}]
# IntegerQueue: set' [{"DestRegister": int, "OpAIsReady": bool, "OpARegTag": int, "OpAValue": int, "OpBIsReady": bool, "OpBRegTag": int, "OpBValue": int, "OpCode": str, "PC": int}]

# INPUT must be a list
if type(INPUT) != list:
    print(f"[{RED}Error{RESET}] The input JSON must be a list structure")
    exit(1)

# Reference should be always a list
if type(REFERENCE) != list:
    print("The reference JSON should be a list. Please check if you pick a wrong reference file.")
    print("If the reference fils is not wrong, please contact TA for more information.")
    exit(2)


def render_value(value) -> str:
    return json.dumps(value, sort_keys=True)


def print_mismatch(path: str, reference, actual) -> None:
    print(f"[{RED}Error{RESET}] Mismatch at {path}")
    print(f"  reference: {GREEN}{render_value(reference)}{RESET}")
    print(f"  your file: {RED}{render_value(actual)}{RESET}")


def compareIntegerQueueEntry(i: dict, r: dict, path: str) -> bool:
    '''
        @return true if i and r are the same
    '''

    types = {
        "DestRegister": int,

        "OpAIsReady": bool,
        "OpARegTag": int,
        "OpAValue": int,

        "OpBIsReady": bool,
        "OpBRegTag": int,
        "OpBValue": int,

        "OpCode": str,

        "PC": int,
    }

    # Check the reference
    for n, t in types.items():
        if not n in r:
            print(f"The reference integer queue entry has wrong format. Missing term: {n}. Raw: {r}.")
            print("Please check if the reference file is correct.")
            exit(2)

        if type(r[n]) != t:
            print(f"Wrong type for integer queue entry {n}. Raw: {r}.")
            print("Please check if the reference file is correct.")
            exit(2)

    # Compare the entry
    for exact_entry in ["PC", "OpCode", "DestRegister", "OpAIsReady", "OpBIsReady"]:
        if not exact_entry in i:
            print(f"[{RED}Error{RESET}][IntegerQueue] Missing property at {path}: {exact_entry}.")
            return False

        # type check
        if type(i[exact_entry]) != type(r[exact_entry]):
            print(f"[{RED}Error{RESET}][IntegerQueue] Property type mismatched at {path}.{exact_entry}.")
            print(f"  reference type: {GREEN}{type(r[exact_entry]).__name__}{RESET}")
            print(f"  your file type: {RED}{type(i[exact_entry]).__name__}{RESET}")
            return False

        # Compare
        if i[exact_entry] != r[exact_entry]:
            print_mismatch(f"{path}.{exact_entry}", r[exact_entry], i[exact_entry])
            if exact_entry == "PC":
                print(f"[{RED}Error{RESET}][IntegerQueue] A PC mismatching usually means you are missing entries for some instructions.")

            return False

    # Now check the operand
    for op in ["A", "B"]:
        if i[f"Op{op}IsReady"]:
            # Check the value
            if not f"Op{op}Value" in i:
                print(f"[{RED}Error{RESET}][IntegerQueue] Missing property at {path}: Op{op}Value.")
                return False
            if i[f"Op{op}Value"] != r[f"Op{op}Value"]:
                print_mismatch(f"{path}.Op{op}Value", r[f"Op{op}Value"], i[f"Op{op}Value"])
                return False
        else:
            if not f"Op{op}RegTag" in i:
                print(f"[{RED}Error{RESET}][IntegerQueue] Missing property at {path}: Op{op}RegTag.")
                return False
            if i[f"Op{op}RegTag"] != r[f"Op{op}RegTag"]:
                print_mismatch(f"{path}.Op{op}RegTag", r[f"Op{op}RegTag"], i[f"Op{op}RegTag"])
                return False

    return True


def compareIntegerQueue(i: list[dict], r: list[dict], path: str) -> bool:
    # check whether each entry has the PC.

    for el in r:
        if not "PC" in el:
            print("All integer queue entry in reference output should have property 'PC'. ")
            print("Please check if the reference file is correct.")
            exit(2)

    for el in i:
        if not "PC" in el:
            print(f"[{RED}Error{RESET}][IntegerQueue] All integer queue entries in your file should have property 'PC'. ")
            return False

    # Now, sort the list by the PC.
    i.sort(key=lambda x: x["PC"])
    r.sort(key=lambda x: x["PC"])

    # First, compare the element count
    if len(i) != len(r):
        print_mismatch(f"{path}.length", len(r), len(i))
        print(f"[{RED}Error{RESET}][IntegerQueue] This usually means you are missing some instructions, or you have more instructions retired later.")
        return False

    # Then, compare each element
    for idx in range(len(r)):
        entry_path = f"{path}[{idx}]"
        if compareIntegerQueueEntry(i[idx], r[idx], entry_path) == False:
            return False

    return True


def compareActiveListEntry(i: dict, r: dict, path: str) -> bool:
    types = {
        "Done": bool,
        "Exception": bool,
        "LogicalDestination": int,
        "OldDestination": int,
        "PC": int
    }

    # Check the reference
    for idx, t in types.items():
        if not idx in r:
            print(f"Missing property in active list entry: {idx}. Raw:{r}")
            print("Please check if the reference file is correct.")
            exit(2)

        if type(r[idx]) != t:
            print(f"Wrong type in the active list entry: {idx}. Expectation: {t}")
            print("Please check if the reference file is correct.")
            print(2)

    # Now, check the value of the entry
    for idx, t in types.items():
        if not idx in i:
            print(f"[{RED}Error{RESET}][ActiveList] Missing property at {path}: {idx}")
            return False

        # check the type
        if type(i[idx]) != t:
            print(f"[{RED}Error{RESET}][ActiveList] Property type mismatched at {path}.{idx}.")
            print(f"  reference type: {GREEN}{t.__name__}{RESET}")
            print(f"  your file type: {RED}{type(i[idx]).__name__}{RESET}")
            return False

        # Do comparison
        if i[idx] != r[idx]:
            print_mismatch(f"{path}.{idx}", r[idx], i[idx])
            return False

    return True


def compareActiveList(i: list[dict], r: list[dict], path: str) -> bool:
    # Make sure their count is the same
    if len(i) != len(r):
        print_mismatch(f"{path}.length", len(r), len(i))
        return False

    for idx in range(len(i)):
        if compareActiveListEntry(i[idx], r[idx], f"{path}[{idx}]") == False:
            print(f"[{RED}Error{RESET}][ActiveList] Active list entry at index {idx} is different.")
            return False

    return True


def compareCycleData(i: dict, r: dict, cycle_idx: int) -> bool:
    cycle_path = f"Cycle[{cycle_idx}]"
    types = {
        "ActiveList": list,
        "BusyBitTable": list,
        "DecodedPCs": list,
        "Exception": bool,
        "ExceptionPC": int,
        "FreeList": list,
        "IntegerQueue": list,
        "PC": int,
        "PhysicalRegisterFile": list,
        "RegisterMapTable": list
    }

    # First, make sure the reference has the correct entry and type.
    for n, t in types.items():
        if not n in r:
            print(f"Missing property in the cycle data in the reference input: {n}")
            print("Please check if the reference file is correct.")
            exit(2)

        if type(r[n]) != t:
            print(f"Wrong type of the property in the cycle data in the reference input: {n}. The expected type is {t}")
            print("Please check if the reference file is correct.")
            exit(2)

    types.pop("ExceptionPC")

    # Second, check user's input to make sure they have the correct type.
    for n, t in types.items():
        if not n in i:
            print(f"[{RED}Error{RESET}][CycleData] Missing property in your file at {cycle_path}.{n}")
            return False

        if type(i[n]) != t:
            print(f"[{RED}Error{RESET}][CycleData] Property type mismatched at {cycle_path}.{n}.")
            print(f"  reference type: {GREEN}{t.__name__}{RESET}")
            print(f"  your file type: {RED}{type(i[n]).__name__}{RESET}")
            return False

    # Now, it is time to check each entry.
    if compareActiveList(i["ActiveList"], r["ActiveList"], f"{cycle_path}.ActiveList") == False:
        print(f"[{RED}Error{RESET}][CycleData] Active list mismatched!")
        return False

    for directed_check in ["BusyBitTable", "DecodedPCs", "Exception", "PC", "PhysicalRegisterFile", "RegisterMapTable"]:
        if i[directed_check] != r[directed_check]:
            print_mismatch(f"{cycle_path}.{directed_check}", r[directed_check], i[directed_check])
            return False

    if set(i["FreeList"]) != set(r["FreeList"]):
        print_mismatch(f"{cycle_path}.FreeList", sorted(r["FreeList"]), sorted(i["FreeList"]))
        return False

    if compareIntegerQueue(i["IntegerQueue"], r["IntegerQueue"], f"{cycle_path}.IntegerQueue") == False:
        print(f"[{RED}Error{RESET}][CycleData] Integer queue mismatched!")
        return False

    if r["Exception"] == True:
        # compare ExceptionPC
        if not "ExceptionPC" in i:
            print(f"[{RED}Error{RESET}][CycleData] Missing property ExceptionPC.")
            return False

        if type(i["ExceptionPC"]) != int:
            print(f"[{RED}Error{RESET}][CycleData] Type mismatched: Property ExceptionPC should be an integer.")
            return False

        if r["ExceptionPC"] != i["ExceptionPC"]:
            print_mismatch(f"{cycle_path}.ExceptionPC", r["ExceptionPC"], i["ExceptionPC"])
            return False

    return True


# Compare only the cycles available in both files.
limit = min(len(INPUT), len(REFERENCE))

if limit == 0:
    print(f"[{RED}Error{RESET}][CycleData] No cycles available to compare!")
    exit(1)

if len(INPUT) != len(REFERENCE):
    print(
        f"Comparing first {limit} cycles only "
        f"(input={len(INPUT)}, reference={len(REFERENCE)})."
    )

for i in range(limit):
    if compareCycleData(INPUT[i], REFERENCE[i], i) == False:
        print(f"[{RED}Error{RESET}][CycleData] Cycle {i} data mismatched. Exit.")
        exit(1)

print(f"{GREEN}PASSED!{RESET} Compared {limit} cycles.")
