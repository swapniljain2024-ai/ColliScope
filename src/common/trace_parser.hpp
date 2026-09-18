#pragma once

#include <string>
#include <vector>
#include <optional>
#include <sstream>
#include <fstream>
#include <stdexcept>
#include <cctype>

namespace colliscope {

enum class TraceOp {
    ENTER_SCOPE,
    EXIT_SCOPE,
    DECLARE,
    REFERENCE
};

inline std::string toString(TraceOp op) {
    switch (op) {
        case TraceOp::ENTER_SCOPE: return "ENTER_SCOPE";
        case TraceOp::EXIT_SCOPE: return "EXIT_SCOPE";
        case TraceOp::DECLARE: return "DECLARE";
        case TraceOp::REFERENCE: return "REFERENCE";
    }
    return "UNKNOWN";
}

struct TraceCommand {
    TraceOp op;
    uint32_t line_number{0};
    std::string identifier{""};
    uint32_t scope_id{0};
    std::optional<uint32_t> parent_scope_id{std::nullopt};
    int64_t type_id{1};

    bool operator==(const TraceCommand& other) const {
        return op == other.op &&
               line_number == other.line_number &&
               identifier == other.identifier &&
               scope_id == other.scope_id &&
               parent_scope_id == other.parent_scope_id &&
               type_id == other.type_id;
    }
};

class TraceParser {
public:
    static std::vector<TraceCommand> parseString(const std::string& content) {
        std::istringstream iss(content);
        return parseStream(iss);
    }

    static std::vector<TraceCommand> parseFile(const std::string& filepath) {
        std::ifstream file(filepath);
        if (!file.is_open()) {
            throw std::runtime_error("Could not open trace file: " + filepath);
        }
        return parseStream(file);
    }

    static std::vector<TraceCommand> parseStream(std::istream& in) {
        std::vector<TraceCommand> commands;
        std::string line;
        uint32_t line_number = 0;

        while (std::getline(in, line)) {
            line_number++;
            
            // Trim leading/trailing whitespace
            size_t start = line.find_first_not_of(" \t\r\n");
            if (start == std::string::npos) {
                continue; // blank line
            }
            if (line[start] == '#') {
                continue; // comment line
            }

            // Remove trailing comments or whitespace
            size_t comment_pos = line.find('#', start);
            std::string active_line = (comment_pos != std::string::npos) 
                                      ? line.substr(start, comment_pos - start)
                                      : line.substr(start);

            std::istringstream line_stream(active_line);
            std::string op_str;
            if (!(line_stream >> op_str)) {
                continue;
            }

            TraceCommand cmd;
            cmd.line_number = line_number;

            if (op_str == "ENTER_SCOPE") {
                cmd.op = TraceOp::ENTER_SCOPE;
                std::string scope_str;
                if (!(line_stream >> scope_str)) {
                    throw std::runtime_error("Trace parse error on line " + std::to_string(line_number) +
                                             ": ENTER_SCOPE missing scope_id");
                }
                cmd.scope_id = parseUint32(scope_str, line_number, "scope_id");

                std::string parent_str;
                if (line_stream >> parent_str) {
                    cmd.parent_scope_id = parseUint32(parent_str, line_number, "parent_scope_id");
                }
            } else if (op_str == "EXIT_SCOPE") {
                cmd.op = TraceOp::EXIT_SCOPE;
                std::string scope_str;
                if (!(line_stream >> scope_str)) {
                    throw std::runtime_error("Trace parse error on line " + std::to_string(line_number) +
                                             ": EXIT_SCOPE missing scope_id");
                }
                cmd.scope_id = parseUint32(scope_str, line_number, "scope_id");
            } else if (op_str == "DECLARE") {
                cmd.op = TraceOp::DECLARE;
                if (!(line_stream >> cmd.identifier)) {
                    throw std::runtime_error("Trace parse error on line " + std::to_string(line_number) +
                                             ": DECLARE missing identifier");
                }
                validateIdentifier(cmd.identifier, line_number);

                std::string type_str;
                if (line_stream >> type_str) {
                    cmd.type_id = parseInt64(type_str, line_number, "type_id");
                }
                std::string scope_str;
                if (line_stream >> scope_str) {
                    cmd.scope_id = parseUint32(scope_str, line_number, "scope_id");
                }
            } else if (op_str == "REFERENCE") {
                cmd.op = TraceOp::REFERENCE;
                if (!(line_stream >> cmd.identifier)) {
                    throw std::runtime_error("Trace parse error on line " + std::to_string(line_number) +
                                             ": REFERENCE missing identifier");
                }
                validateIdentifier(cmd.identifier, line_number);

                std::string scope_str;
                if (line_stream >> scope_str) {
                    cmd.scope_id = parseUint32(scope_str, line_number, "scope_id");
                }
            } else {
                throw std::runtime_error("Trace parse error on line " + std::to_string(line_number) +
                                         ": Unknown operation '" + op_str + "'");
            }

            commands.push_back(cmd);
        }

        return commands;
    }

private:
    static uint32_t parseUint32(const std::string& s, uint32_t line_num, const std::string& field) {
        try {
            size_t idx = 0;
            unsigned long val = std::stoul(s, &idx);
            if (idx != s.size()) {
                throw std::runtime_error("Invalid character in numeric field");
            }
            return static_cast<uint32_t>(val);
        } catch (...) {
            throw std::runtime_error("Trace parse error on line " + std::to_string(line_num) +
                                     ": Malformed integer for " + field + " ('" + s + "')");
        }
    }

    static int64_t parseInt64(const std::string& s, uint32_t line_num, const std::string& field) {
        try {
            size_t idx = 0;
            long long val = std::stoll(s, &idx);
            if (idx != s.size()) {
                throw std::runtime_error("Invalid character in numeric field");
            }
            return static_cast<int64_t>(val);
        } catch (...) {
            throw std::runtime_error("Trace parse error on line " + std::to_string(line_num) +
                                     ": Malformed integer for " + field + " ('" + s + "')");
        }
    }

    static void validateIdentifier(const std::string& id, uint32_t line_num) {
        if (id.empty()) {
            throw std::runtime_error("Trace parse error on line " + std::to_string(line_num) +
                                     ": Empty identifier");
        }
        if (!std::isalpha(static_cast<unsigned char>(id[0])) && id[0] != '_') {
            throw std::runtime_error("Trace parse error on line " + std::to_string(line_num) +
                                     ": Identifier must start with letter or underscore ('" + id + "')");
        }
        for (char c : id) {
            if (!std::isalnum(static_cast<unsigned char>(c)) && c != '_') {
                throw std::runtime_error("Trace parse error on line " + std::to_string(line_num) +
                                         ": Invalid character in identifier ('" + id + "')");
            }
        }
    }
};

} // namespace colliscope
