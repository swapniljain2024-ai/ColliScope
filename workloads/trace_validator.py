"""
ColliScope Trace Validator (Python)
Validates execution traces according to docs/trace_format.md.
"""

from dataclasses import dataclass
from typing import Optional, List
import re

IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

@dataclass
class TraceCommand:
    op: str
    line_number: int
    identifier: Optional[str] = None
    scope_id: Optional[int] = None
    parent_scope_id: Optional[int] = None
    type_id: Optional[int] = None

class TraceValidator:
    @staticmethod
    def parse_string(content: str) -> List[TraceCommand]:
        lines = content.splitlines()
        commands = []

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Strip inline comment
            if '#' in line:
                line = line[:line.index('#')].strip()
                if not line:
                    continue

            tokens = line.split()
            opcode = tokens[0].upper()

            if opcode == "ENTER_SCOPE":
                if len(tokens) < 2:
                    raise ValueError(f"Trace parse error on line {line_num}: ENTER_SCOPE missing scope_id")
                try:
                    scope_id = int(tokens[1])
                except ValueError:
                    raise ValueError(f"Trace parse error on line {line_num}: Malformed scope_id '{tokens[1]}'")
                parent_id = None
                if len(tokens) >= 3:
                    try:
                        parent_id = int(tokens[2])
                    except ValueError:
                        raise ValueError(f"Trace parse error on line {line_num}: Malformed parent_scope_id '{tokens[2]}'")
                commands.append(TraceCommand(op=opcode, line_number=line_num, scope_id=scope_id, parent_scope_id=parent_id))

            elif opcode == "EXIT_SCOPE":
                if len(tokens) < 2:
                    raise ValueError(f"Trace parse error on line {line_num}: EXIT_SCOPE missing scope_id")
                try:
                    scope_id = int(tokens[1])
                except ValueError:
                    raise ValueError(f"Trace parse error on line {line_num}: Malformed scope_id '{tokens[1]}'")
                commands.append(TraceCommand(op=opcode, line_number=line_num, scope_id=scope_id))

            elif opcode == "DECLARE":
                if len(tokens) < 2:
                    raise ValueError(f"Trace parse error on line {line_num}: DECLARE missing identifier")
                identifier = tokens[1]
                if not IDENTIFIER_PATTERN.match(identifier):
                    raise ValueError(f"Trace parse error on line {line_num}: Invalid identifier '{identifier}'")
                type_id = 1
                scope_id = None
                if len(tokens) >= 3:
                    try:
                        type_id = int(tokens[2])
                    except ValueError:
                        raise ValueError(f"Trace parse error on line {line_num}: Malformed type_id '{tokens[2]}'")
                if len(tokens) >= 4:
                    try:
                        scope_id = int(tokens[3])
                    except ValueError:
                        raise ValueError(f"Trace parse error on line {line_num}: Malformed scope_id '{tokens[3]}'")
                commands.append(TraceCommand(op=opcode, line_number=line_num, identifier=identifier, type_id=type_id, scope_id=scope_id))

            elif opcode == "REFERENCE":
                if len(tokens) < 2:
                    raise ValueError(f"Trace parse error on line {line_num}: REFERENCE missing identifier")
                identifier = tokens[1]
                if not IDENTIFIER_PATTERN.match(identifier):
                    raise ValueError(f"Trace parse error on line {line_num}: Invalid identifier '{identifier}'")
                scope_id = None
                if len(tokens) >= 3:
                    try:
                        scope_id = int(tokens[2])
                    except ValueError:
                        raise ValueError(f"Trace parse error on line {line_num}: Malformed scope_id '{tokens[2]}'")
                commands.append(TraceCommand(op=opcode, line_number=line_num, identifier=identifier, scope_id=scope_id))

            else:
                raise ValueError(f"Trace parse error on line {line_num}: Unknown operation '{opcode}'")

        return commands

    @classmethod
    def parse_file(cls, filepath: str) -> List[TraceCommand]:
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.parse_string(f.read())
