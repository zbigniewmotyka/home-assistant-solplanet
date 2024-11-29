"""Constants for the Solplanet integration."""

DOMAIN = "solplanet"
MANUFACTURER = "Solplanet"

INVERTER_IDENTIFIER = "inverter"
BATTERY_IDENTIFIER = "battery"
METER_IDENTIFIER = "meter"

CONF_INTERVAL = "interval"
DEFAULT_INTERVAL = 60

INVERTER_ERROR_CODES = {
    0: "No error",
    1: "1 - Communication Fails Between M-S",
    2: "2 - EEPROM R/W Fail",
    3: "3 - Relay Check Fail",
    4: "4 - DC Injection High",
    5: "5 - The result of Auto Test Function is fail",
    6: "6 - DC Bus Voltage Value High",
    7: "7 - The voltage reference inside is abnormal",
    8: "8 - AC HCT Failure",
    9: "9 - GFCI Device Failure",
    10: "10 - Device fault",
    11: "11 - M-S version unmatch",
    12: "12 - Reserved",
    13: "13 - Reserve, unknown error",
    14: "14 - Reserve, unknown error",
    15: "15 - Reserve, unknown error",
    16: "16 - Reserve, unknown error",
    17: "17 - Reserve, unknown error",
    18: "18 - Reserve, unknown error",
    19: "19 - Reserve, unknown error",
    20: "20 - Reserve, unknown error",
    21: "21 - Reserve, unknown error",
    22: "22 - Reserve, unknown error",
    23: "23 - Reserve, unknown error",
    24: "24 - Reserve, unknown error",
    25: "25 - Reserve, unknown error",
    26: "26 - Reserve, unknown error",
    27: "27 - Reserve, unknown error",
    28: "28 - Reserve, unknown error",
    29: "29 - Reserve, unknown error",
    30: "30 - Reserve, unknown error",
    31: "31 - Reserve, unknown error",
    32: "32 - ROCOF Fault",
    33: "33 - Fac Failure:Fac Out of Range",
    34: "34 - AC Voltage Out Of Range",
    35: "35 - Utility Loss",
    36: "36 - GFCI Failure",
    37: "37 - PV Over Voltage",
    38: "38 - ISO Fault",
    39: "39 - Fan Lock",
    40: "40 - Over Temperature In Inverter",
    41: "41 - Consistent Fault:Vac differs for M-S",
    42: "42 - Consistent Fault:Fac differs for M-S",
    43: "43 - Consistent Fault:Ground I differs for M-S",
    44: "44 - Consistent Fault:DC inj. Differs for M-S",
    45: "45 - Consistent Fault:Fac,Vac differs for M-S",
    46: "46 - High DC bus",
    47: "47 - Consistent Fault",
    48: "48 - Average volt of ten minutes Fault",
    49: "49 - PV1-SPD Fault",
    50: "50 - PV2-SPD Fault",
    51: "51 - Fuse Fault",
    52: "52 - Miss N Fault",
    53: "53 - ISO check:before enable constant current,ISO voltage > 300mv",
    54: "54 - ISO check:after enable constant current,ISO voltage out of range(1.37v+/-20%)",
    55: "55 - ISO check:N P relay change,ISO voltage sudden below 40mv",
    56: "56 - GFCI protect fault:30mA level",
    57: "57 - GFCI protect fault:60mA level",
    58: "58 - GFCI protect fault:150mA level",
    59: "59 - PV1 string current abnormal",
    60: "60 - PV2 string current abnormal",
    61: "61 - DRMS Communication Fails(S9 Open)",
    62: "62 - DRMS order disconnection device(S0 Close)",
    63: "63 - L-PE Short Circuit Fault",
    64: "64 - PV input mode error",
    65: "65 - PE Connection Fault",
    66: "66 - Reserve, unknown error",
    67: "67 - Reserve, unknown error",
    68: "68 - Reserve, unknown error",
    69: "69 - Reserve, unknown error",
    70: "70 - AFCI Self-Test failed(Including AFCI detection circuit fault and CAN circult fault)",
    71: "71 - Photovoltaic arcing fault occurs or Poor circuit contact",
    72: "72 - Reserve, unknown error",
    73: "73 - Reserve, unknown error",
    74: "74 - Reserve, unknown error",
    75: "75 - Reserve, unknown error",
    76: "76 - Reserve, unknown error",
    77: "77 - Reserve, unknown error",
    78: "78 - Reserve, unknown error",
    79: "79 - Reserve, unknown error",
    80: "80 - Reserve, unknown error",
    81: "81 - Reserve, unknown error",
    305: "305 - Inverter Offline",
    2000: "2000 - DischgOverCur",
    2001: "2001 - Over Load",
    2002: "2002 - BatDisconnect",
    2003: "2003 - Bat Under Vol",
    2004: "2004 - BatLow capacity",
    2005: "2005 - Bat Over Vol",
    2006: "2006 - Grid low vol",
    2007: "2007 - Grid low vol",
    2008: "2008 - Grid low freq",
    2009: "2009 - Grid overFreq",
    2010: "2010 - Gfci over",
    2011: "2011 - ParallelCANFail",
    2012: "2012 - Grid CT Reverse",
    2013: "2013 - Bus under vol",
    2014: "2014 - Bus over vol",
    2015: "2015 - Inv over cur",
    2016: "2016 - Chg over cur",
    2017: "2017 - BUS Volt OSC",
    2018: "2018 - Inv under vol",
    2019: "2019 - Inv over vol",
    2020: "2020 - InvFreqAbnor",
    2021: "2021 - IGBT temp high",
    2023: "2023 - Bat over temp",
    2024: "2024 - Bat UnderTemp",
    2027: "2027 - BMS comm.fail",
    2028: "2028 - Fan fail",
    2030: "2030 - Grid Phase error",
    2031: "2031 - Arc Fault",
    2032: "2032 - Bus soft fail",
    2033: "2033 - Inv soft fail",
    2034: "2034 - Bus short",
    2035: "2035 - Inv short",
    2037: "2037 - PV iso low",
    2038: "2038 - Bus Relay Fault",
    2039: "2039 - Grid Relay Fault",
    2040: "2040 - EPS rly fault",
    2041: "2041 - Gfci fault",
    2042: "2042 - CT fault",
    2043: "2043 - PV short",
    2044: "2044 - Byp relay fault",
    2045: "2045 - System fault",
    2046: "2046 - Current DCover",
    2047: "2047 - Voltage DCover",
}
INVERTER_STATUS = {
    0: "Wait",
    1: "Normal",
    2: "Fault",
    4: "Checking",
}
BATTERY_COMMUNICATION_STATUS = {
    10: "Normal",
    11: "Virtual battery",
}
BATTERY_STATUS = {
    1: "Idle",
    2: "Charging",
    3: "Discharging",
    4: "Fault",
}
BATTERY_ERRORS_1 = {
    0: "Communication data error",
    1: "Electric core or module overvoltage",
    2: "Electric core or module undervoltage",
    3: "Electric core temperature is too high",
    4: "Electric core temperature is too low",
    5: "Discharge overcurrent",
    6: "Charge overcurrent",
    7: "Internal communication error",
    8: "Electric core imbalance",
    9: "Low system insulation",
    10: "Voltage sensor failure",
    11: "Temperature sensor failure",
    12: "Contactor failure",
    13: "Power-on self-test failure",
    14: "IC self test failure",
}
BATTERY_ERRORS_2 = {
    0: "Battery voltage self-test failure",
    1: "System voltage self-test failure",
    2: "System insulation self check failure",
    3: "RTC failure",
    4: "EEPROM failure",
    5: "Flash failure",
    6: "AFE failure",  # codespell:ignore
    7: "Insulation sampling IC failure",
    9: "Current sampling IC failure",
    10: "HDC failure",
    11: "Daisy chain failure",
    12: "Pre charge failure",
}
BATTERY_ERRORS_3 = {
    0: "Battery damage and failure",
    1: "Input voltage failure",
    2: "Input reverse failure",
    3: "Circuit breaker failure",
}
BATTERY_ERRORS_4: dict[int, str] = {}
BATTERY_WARNINGS_1 = {
    0: "Communication data error",
    1: "Electric core or module voltage is high",
    2: "Electric core or module voltage is low",
    3: "Electric core temperature is too high",
    4: "Electric core temperature is too low",
    5: "High discharge current",
    6: "High charging current",
    7: "Internal communication failed",
    8: "Electric core imbalance",
    9: "Low system insulation",
}
BATTERY_WARNINGS_2: dict[int, str] = {}
BATTERY_WARNINGS_3: dict[int, str] = {}
BATTERY_WARNINGS_4: dict[int, str] = {}
