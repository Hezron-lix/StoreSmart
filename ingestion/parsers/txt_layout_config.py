"""Fixed-width layout for the mainframe TXT source - SINGLE SOURCE OF TRUTH.

=========================== READ THIS BEFORE EDITING ==========================
The slices below were derived by inspecting the supplied hackathon sample file
(`sample_mainframe_fixed.txt`, 10,500 records) and verified against every
record in it: all fields parsed cleanly with zero failures.

They are NOT guessed - but they are also NOT an official published copybook.
If the organizers hand you an official record layout, PASTE ITS POSITIONS HERE
and change nothing else in the codebase.

Verified sample record (52 characters):

    DMP00000012020092709391759294321SUPPORT   POL-MKT-3Y
    |________||______||____||______||________||________|
     0      9 10   17 18 23 24   31 32     41 42     51
     record   date     time   size    owner_dept policy_id
     id       YYYYMMDD HHMMSS (KB)    (padded)   (padded)

Slices are Python-style [start, end) and 0-based.
===============================================================================
"""

# --- field positions ---------------------------------------------------------
TXT_LAYOUT = {
    "record_id": (0, 10),    # e.g. "DMP0000001"
    "date": (10, 18),        # YYYYMMDD
    "time": (18, 24),        # HHMMSS
    "size": (24, 32),        # 8 digits, zero-padded
    "owner_dept": (32, 42),  # left-aligned, space padded
    "policy_id": (42, 52),   # left-aligned, space padded
}

EXPECTED_LINE_LENGTH = 52

# --- units and formats -------------------------------------------------------
# ASSUMPTION TO CONFIRM WITH THE ORGANIZERS: the 8-digit size column carries no
# unit marker. Sample values range 5,337 - 99,995,630, which as KB gives roughly
# 5 MB - 95 GB per record - the only unit that yields sensible sizes.
# If the official layout says otherwise, change this ONE constant.
SIZE_UNIT = "KB"

DATE_FORMAT = "%Y%m%d"
TIME_FORMAT = "%H%M%S"

# --- known data quirk --------------------------------------------------------
# The supplied sample contains a generator defect: the owner_dept column is 10
# characters wide, but the value "ENGINEERING" is 11 characters. Those lines are
# 53 characters long and every field after owner_dept is shifted right by one,
# so a strict slice reads the policy as "GPOL-ENG-3Y" instead of "POL-ENG-3Y".
# About 1,034 of 10,500 sample records are affected.
#
# When True, the parser re-aligns such lines on the policy prefix below.
# Set to False to parse strictly by position only.
TOLERATE_DEPT_OVERFLOW = True
POLICY_ID_PREFIX = "POL-"

# Prefix used to confirm a line is a data record (not a header/footer/banner).
RECORD_ID_PREFIX = "DMP"
