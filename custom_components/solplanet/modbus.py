"""Solplanet Modbus RTU frame generator and response decoder."""

import contextlib
import enum
import struct


class DataType(enum.Enum):
    """Enum for supported data types in Modbus communications."""

    B16 = "B16"  # Bit field (16-bit)
    B32 = "B32"  # Bit field (32-bit)
    S16 = "S16"  # Signed integer (16-bit)
    U16 = "U16"  # Unsigned integer (16-bit)
    S32 = "S32"  # Signed integer (32-bit)
    U32 = "U32"  # Unsigned integer (32-bit)
    E16 = "E16"  # Number code (16-bit)
    STRING = "String"  # String type (16-bit, two 8-bit ASCII characters)


class ModbusRtuFrameGenerator:
    """A class to generate and decode Modbus RTU frames for various Modbus functions."""

    # Definition of NaN values for different data types as class attribute
    NAN_VALUES: dict[DataType, int] = {
        DataType.B16: 0xFFFF,
        DataType.B32: 0xFFFFFFFF,
        DataType.S16: 0x8000,
        DataType.U16: 0xFFFF,
        DataType.S32: 0x80000000,
        DataType.U32: 0xFFFFFFFF,
        DataType.E16: 0xFFFF,
        DataType.STRING: 0x0000,
    }

    # Value ranges for validation
    VALUE_RANGES: dict[DataType, tuple[int, int]] = {
        DataType.B16: (0, 0xFFFF),
        DataType.U16: (0, 0xFFFF),
        DataType.E16: (0, 0xFFFF),
        DataType.B32: (0, 0xFFFFFFFF),
        DataType.U32: (0, 0xFFFFFFFF),
        DataType.S16: (-32768, 32767),
        DataType.S32: (-2147483648, 2147483647),
    }

    def generate_read_holding_register_frame(
        self, device_id: int, register_address: int, register_length: int
    ) -> str:
        """Generate Modbus RTU frame for Read Holding Register function (Function Code: 0x03)."""
        register_offset = register_address - 40001
        return self._generate_frame(device_id, 0x03, register_offset, register_length)

    def generate_read_input_register_frame(
        self, device_id: int, register_address: int, register_length: int
    ) -> str:
        """Generate Modbus RTU frame for Read Input Register function (Function Code: 0x04)."""
        register_offset = register_address - 30001
        return self._generate_frame(device_id, 0x04, register_offset, register_length)

    def generate_write_single_holding_register_frame(
        self, device_id: int, register_address: int, value, data_type: DataType
    ) -> str:
        """Generate Modbus RTU frame for Write Single Holding Register function (Function Code: 0x06)."""
        register_offset = register_address - 40001
        encoded_value = self.encode_request_data(value, data_type)
        return self._generate_frame(device_id, 0x06, register_offset, encoded_value)

    def _generate_frame(
        self, device_id: int, function_code: int, register_offset: int, value: int
    ) -> str:
        """Generate Modbus RTU frame for the specified function code."""
        if not (0 <= device_id <= 0xFF):
            raise ValueError("Invalid device ID (0-255).")
        if not (0 <= register_offset <= 0xFFFF):
            raise ValueError("Invalid register offset (0-65535).")
        if not (0 <= value <= 0xFFFF):
            raise ValueError("Invalid value (0-65535).")

        frame = struct.pack(
            ">B B H H", device_id, function_code, register_offset, value
        )
        crc = self._calculate_crc(frame)
        frame += struct.pack("<H", crc)  # Add CRC in little-endian order

        return frame.hex()

    def decode_response(
        self, response_hex: str, data_type: DataType
    ) -> dict | int | str | None:
        """Decode Modbus RTU response based on function code and data type."""
        response = bytes.fromhex(response_hex)

        if len(response) < 5:
            raise ValueError("Invalid response length.")

        device_id, function_code = struct.unpack(">B B", response[:2])

        # Use a more concise approach to function code routing
        if function_code in (0x03, 0x04):
            return self._decode_register_response(response, data_type)
        if function_code == 0x06:
            return self._decode_write_single_holding_register_response(response)
        if function_code in [0x83, 0x84, 0x86]:
            return self._decode_error_response(response)

        raise ValueError("Unsupported function code in response.")

    def _verify_crc(self, response: bytes) -> None:
        """Verify CRC in the response."""
        received_crc = struct.unpack("<H", response[-2:])[0]
        calculated_crc = self._calculate_crc(response[:-2])

        if received_crc != calculated_crc:
            raise ValueError("CRC error: checksums do not match.")

    def _decode_write_single_holding_register_response(
        self, response: bytes
    ) -> dict[str, int]:
        """Decode Modbus RTU response for Write Single Holding Register function (Function Code: 0x06)."""
        if len(response) != 8:
            raise ValueError("Invalid response length.")

        self._verify_crc(response)

        device_id, function_code, register_address, data = struct.unpack(
            ">B B H H", response[:6]
        )

        return {
            "device_id": device_id,
            "function_code": function_code,
            "register_address": register_address,
            "data": data,
        }

    def _decode_register_response(
        self, response: bytes, data_type: DataType
    ) -> int | str | None:
        """Decode Modbus RTU response for Read Holding Register and Read Input Register functions."""
        device_id, function_code, byte_count = struct.unpack(">B B B", response[:3])
        data = response[3:-2]

        self._verify_crc(response)

        # Handle different data types based on length requirements
        if data_type in [DataType.S32, DataType.U32, DataType.B32]:
            if len(data) < 4:
                raise ValueError(f"Insufficient data for type {data_type.value}")

            # For 32-bit types we need 4 bytes (2 registers)
            high_word = struct.unpack(">H", data[0:2])[0]
            low_word = struct.unpack(">H", data[2:4])[0]

            # Combine two 16-bit registers into one 32-bit value
            raw_value = (high_word << 16) | low_word
        else:
            # For 16-bit types we need 2 bytes (1 register)
            if len(data) < 2:
                raise ValueError(f"Insufficient data for type {data_type.value}")

            raw_value = struct.unpack(">H", data[0:2])[0]

        return self._decode_value(raw_value, data_type)

    def _decode_value(self, raw_value: int, data_type: DataType) -> int | str | None:
        """Decode a single value based on data type."""
        if raw_value == self.NAN_VALUES[data_type]:
            return None

        # Simplify handling of unsigned types that just return the raw value
        if data_type in [
            DataType.B16,
            DataType.B32,
            DataType.U16,
            DataType.U32,
            DataType.E16,
        ]:
            return raw_value

        # Handle signed types
        if data_type == DataType.S16:
            return struct.unpack(">h", struct.pack(">H", raw_value))[0]
        if data_type == DataType.S32:
            return struct.unpack(">i", struct.pack(">I", raw_value))[0]

        # Handle string type
        if data_type == DataType.STRING:
            high_byte = (raw_value >> 8) & 0xFF
            low_byte = raw_value & 0xFF
            # Simplified string handling
            result = ""
            if high_byte:
                with contextlib.suppress(ValueError):
                    result += chr(high_byte)
            if low_byte:
                with contextlib.suppress(ValueError):
                    result += chr(low_byte)
            return result

        raise ValueError(f"Unsupported data type: {data_type}")

    def _decode_error_response(self, response: bytes) -> dict[str, int]:
        """Decode Modbus RTU error response."""
        if len(response) != 5:
            raise ValueError("Invalid error response length.")

        self._verify_crc(response)

        device_id, error_function_code, exception_code = struct.unpack(
            ">B B B", response[:3]
        )

        return {
            "device_id": device_id,
            "error_function_code": error_function_code,
            "exception_code": exception_code,
        }

    def _calculate_crc(self, data: bytes) -> int:
        """Calculate CRC-16 checksum for Modbus RTU frame."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def encode_request_data(self, value, data_type: DataType) -> int:
        """Encode value to appropriate format for Modbus RTU request."""
        # Handle None values (NaN)
        if value is None:
            return self.NAN_VALUES[data_type]

        # Validate value range for numeric types
        if data_type in self.VALUE_RANGES:
            min_val, max_val = self.VALUE_RANGES[data_type]
            if not (min_val <= value <= max_val):
                raise ValueError(
                    f"Value for type {data_type.value} must be in range {min_val}-{max_val}"
                )

        # Process based on data type
        if data_type in [
            DataType.B16,
            DataType.U16,
            DataType.E16,
            DataType.B32,
            DataType.U32,
        ]:
            # All unsigned types just return the value
            return value

        if data_type == DataType.S16:
            # Convert signed 16-bit to unsigned representation
            return struct.unpack(">H", struct.pack(">h", value))[0]

        if data_type == DataType.S32:
            # Convert signed 32-bit to unsigned representation
            return struct.unpack(">I", struct.pack(">i", value))[0]

        if data_type == DataType.STRING:
            if not isinstance(value, str) or len(value) > 2:
                raise ValueError(
                    f"Value for type {data_type.value} must be a string with a maximum length of 2 characters"
                )

            # Pad the string to a length of 2 (if it's shorter)
            value = value.ljust(2, "\0")

            # Convert two ASCII characters to a 16-bit value
            high_byte = ord(value[0]) if value[0] else 0
            low_byte = ord(value[1]) if value[1] else 0

            return (high_byte << 8) | low_byte

        raise ValueError(f"Unsupported data type: {data_type}")
