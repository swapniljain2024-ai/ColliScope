#include "third_party/catch2/catch.hpp"
#include "common/trace_parser.hpp"

using namespace colliscope;

TEST_CASE("TraceParser parses valid execution traces", "[trace]") {
    std::string sample_trace = 
        "# Initial comment\n"
        "ENTER_SCOPE 0\n"
        "DECLARE global_x 1 0\n"
        "\n"
        "ENTER_SCOPE 1 0 # with parent scope\n"
        "DECLARE local_y 2 1\n"
        "REFERENCE global_x 1\n"
        "EXIT_SCOPE 1\n"
        "REFERENCE global_x 0\n"
        "EXIT_SCOPE 0\n";

    auto cmds = TraceParser::parseString(sample_trace);
    REQUIRE(cmds.size() == 8);

    REQUIRE(cmds[0].op == TraceOp::ENTER_SCOPE);
    REQUIRE(cmds[0].scope_id == 0);
    REQUIRE(!cmds[0].parent_scope_id.has_value());

    REQUIRE(cmds[1].op == TraceOp::DECLARE);
    REQUIRE(cmds[1].identifier == "global_x");
    REQUIRE(cmds[1].type_id == 1);
    REQUIRE(cmds[1].scope_id == 0);

    REQUIRE(cmds[2].op == TraceOp::ENTER_SCOPE);
    REQUIRE(cmds[2].scope_id == 1);
    REQUIRE(cmds[2].parent_scope_id == 0);

    REQUIRE(cmds[3].op == TraceOp::DECLARE);
    REQUIRE(cmds[3].identifier == "local_y");
    REQUIRE(cmds[3].type_id == 2);

    REQUIRE(cmds[4].op == TraceOp::REFERENCE);
    REQUIRE(cmds[4].identifier == "global_x");
    REQUIRE(cmds[4].scope_id == 1);

    REQUIRE(cmds[5].op == TraceOp::EXIT_SCOPE);
    REQUIRE(cmds[5].scope_id == 1);

    REQUIRE(cmds[6].op == TraceOp::REFERENCE);
    REQUIRE(cmds[6].identifier == "global_x");

    REQUIRE(cmds[7].op == TraceOp::EXIT_SCOPE);
    REQUIRE(cmds[7].scope_id == 0);
}

TEST_CASE("TraceParser rejects malformed traces", "[trace]") {
    SECTION("Unknown opcode") {
        std::string bad = "UNKNOWN_OP foo\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("Unknown operation"));
    }

    SECTION("ENTER_SCOPE missing scope_id") {
        std::string bad = "ENTER_SCOPE\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("missing scope_id"));
    }

    SECTION("EXIT_SCOPE missing scope_id") {
        std::string bad = "EXIT_SCOPE\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("missing scope_id"));
    }

    SECTION("DECLARE missing identifier") {
        std::string bad = "DECLARE\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("missing identifier"));
    }

    SECTION("DECLARE invalid identifier starting with digit") {
        std::string bad = "DECLARE 99var 1 0\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("Identifier must start with letter or underscore"));
    }

    SECTION("REFERENCE missing identifier") {
        std::string bad = "REFERENCE\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("missing identifier"));
    }

    SECTION("Malformed integer in scope_id") {
        std::string bad = "ENTER_SCOPE abc\n";
        REQUIRE_THROWS_WITH(TraceParser::parseString(bad), Catch::Contains("Malformed integer for scope_id"));
    }
}
