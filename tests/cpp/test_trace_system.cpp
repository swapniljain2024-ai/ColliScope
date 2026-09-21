#include "third_party/catch2/catch.hpp"
#include "common/trace_parser.hpp"
#include "common/trace_oracle.hpp"
#include "common/trace_executor.hpp"
#include "chaining_table.hpp"
#include "cuckoo_table.hpp"
#include "hopscotch_table.hpp"
#include "svc_hash/svc_hash_table.hpp"

#include <string>
#include <vector>
#include <memory>
#include <fstream>

using namespace colliscope;

TEST_CASE("TraceParser - Detailed Grammar and Default Scoping", "[trace_system]") {
    SECTION("Omitted parent and scope defaults") {
        std::string trace_text = 
            "ENTER_SCOPE 0\n"
            "DECLARE alpha 10\n"       // scope_id omitted -> defaults to active
            "REFERENCE alpha\n"        // scope_id omitted -> defaults to active
            "ENTER_SCOPE 1\n"          // parent omitted -> defaults to active (0)
            "DECLARE beta\n"           // type_id and scope_id omitted -> type 1, active scope
            "REFERENCE beta\n"
            "EXIT_SCOPE 1\n"
            "EXIT_SCOPE 0\n";

        auto cmds = TraceParser::parseString(trace_text);
        REQUIRE(cmds.size() == 8);

        REQUIRE(cmds[1].op == TraceOp::DECLARE);
        REQUIRE(cmds[1].identifier == "alpha");
        REQUIRE(cmds[1].type_id == 10);
        REQUIRE_FALSE(cmds[1].has_explicit_scope);

        REQUIRE(cmds[2].op == TraceOp::REFERENCE);
        REQUIRE(cmds[2].identifier == "alpha");
        REQUIRE_FALSE(cmds[2].has_explicit_scope);

        REQUIRE(cmds[3].op == TraceOp::ENTER_SCOPE);
        REQUIRE(cmds[3].scope_id == 1);
        REQUIRE_FALSE(cmds[3].parent_scope_id.has_value());

        REQUIRE(cmds[4].op == TraceOp::DECLARE);
        REQUIRE(cmds[4].identifier == "beta");
        REQUIRE(cmds[4].type_id == 1); // default type
        REQUIRE_FALSE(cmds[4].has_explicit_scope);
    }

    SECTION("Malformed trace rejections") {
        REQUIRE_THROWS_WITH(TraceParser::parseString("DECLARE\n"), Catch::Contains("missing identifier"));
        REQUIRE_THROWS_WITH(TraceParser::parseString("REFERENCE\n"), Catch::Contains("missing identifier"));
        REQUIRE_THROWS_WITH(TraceParser::parseString("ENTER_SCOPE\n"), Catch::Contains("missing scope_id"));
        REQUIRE_THROWS_WITH(TraceParser::parseString("EXIT_SCOPE\n"), Catch::Contains("missing scope_id"));
        REQUIRE_THROWS_WITH(TraceParser::parseString("INVALID_OP x\n"), Catch::Contains("Unknown operation"));
        REQUIRE_THROWS_WITH(TraceParser::parseString("DECLARE 123bad 1 0\n"), Catch::Contains("Identifier must start with letter or underscore"));
    }
}

TEST_CASE("TraceOracle - Lexical Scoping and Shadowing Unit Tests", "[trace_system]") {
    TraceOracle oracle;

    REQUIRE(oracle.getAlgorithmName() == "oracle");
    REQUIRE(oracle.getCurrentScopeId() == 0);

    SymbolValue g_val{100, 1, "global"};
    REQUIRE(oracle.insert("x", g_val, 0));

    // Global lookup
    auto res_g = oracle.lookup("x", 0);
    REQUIRE(res_g.has_value());
    REQUIRE(res_g.value().type_id == 100);

    // Enter scope 1
    oracle.enterScope(1, 0);
    REQUIRE(oracle.getCurrentScopeId() == 1);

    // Lookup from child scope resolves global x
    auto res_c1 = oracle.lookup("x", 1);
    REQUIRE(res_c1.has_value());
    REQUIRE(res_c1.value().type_id == 100);

    // Shadow x in scope 1
    SymbolValue s1_val{200, 2, "shadow1"};
    REQUIRE(oracle.insert("x", s1_val, 1));

    // Lookup from scope 1 resolves shadowed declaration
    auto res_s1 = oracle.lookup("x", 1);
    REQUIRE(res_s1.has_value());
    REQUIRE(res_s1.value().type_id == 200);

    // Enter scope 2
    oracle.enterScope(2, 1);
    SymbolValue s2_val{300, 3, "shadow2"};
    REQUIRE(oracle.insert("x", s2_val, 2));

    // Lookup from scope 2 resolves deepest active declaration
    REQUIRE(oracle.lookup("x", 2).value().type_id == 300);

    // Exit scope 2 -> resolves back to scope 1
    oracle.exitScope(2);
    REQUIRE(oracle.getCurrentScopeId() == 1);
    REQUIRE(oracle.lookup("x", 1).value().type_id == 200);

    // Exit scope 1 -> resolves back to scope 0
    oracle.exitScope(1);
    REQUIRE(oracle.getCurrentScopeId() == 0);
    REQUIRE(oracle.lookup("x", 0).value().type_id == 100);

    // Non-existent symbol
    REQUIRE_FALSE(oracle.lookup("non_existent", 0).has_value());
}

TEST_CASE("TraceOracle - Scope Transition Invariants", "[trace_system]") {
    TraceOracle oracle;

    SECTION("Cannot enter scope with inactive/unregistered parent") {
        REQUIRE_THROWS_WITH(oracle.enterScope(2, 99), Catch::Contains("parent scope 99 is not active"));
    }

    SECTION("Cannot enter scope when parent is not the current active scope") {
        oracle.enterScope(1, 0);
        // Current scope is now 1, attempting to enter scope 2 with parent 0 must fail
        REQUIRE_THROWS_WITH(oracle.enterScope(2, 0), Catch::Contains("is not current scope"));
    }

    SECTION("Cannot enter duplicate active scope ID") {
        oracle.enterScope(1, 0);
        REQUIRE_THROWS_WITH(oracle.enterScope(1, 1), Catch::Contains("is already active"));
    }

    SECTION("Cannot exit scope that is not current scope") {
        oracle.enterScope(1, 0);
        oracle.enterScope(2, 1);
        // Current scope is 2, trying to exit 1 must fail
        REQUIRE_THROWS_WITH(oracle.exitScope(1), Catch::Contains("is not current scope"));
    }

    SECTION("Cannot exit inactive scope") {
        oracle.enterScope(1, 0);
        oracle.exitScope(1);
        REQUIRE_THROWS_WITH(oracle.exitScope(1), Catch::Contains("is not current scope"));
    }
}

TEST_CASE("TraceExecutor - Replay sample_lexical.trace against Oracle", "[trace_system]") {
    std::string filepath = "workloads/traces/sample_lexical.trace";
    auto commands = TraceParser::parseFile(filepath);
    REQUIRE_FALSE(commands.empty());

    TraceOracle oracle;
    auto result = TraceExecutor::execute(commands, oracle);

    REQUIRE(result.algorithm_name == "oracle");
    REQUIRE(result.reference_count == 12);
    REQUIRE(result.successful_references == 10);
    REQUIRE(result.failed_references == 2);
    REQUIRE(result.reference_results.size() == 12);

    // Index 0: global_var in scope 0 -> 100
    REQUIRE(result.reference_results[0].has_value());
    REQUIRE(result.reference_results[0]->type_id == 100);

    // Index 1: count in scope 0 -> 1
    REQUIRE(result.reference_results[1].has_value());
    REQUIRE(result.reference_results[1]->type_id == 1);

    // Index 2: count in scope 1 -> 2 (shadowed)
    REQUIRE(result.reference_results[2].has_value());
    REQUIRE(result.reference_results[2]->type_id == 2);

    // Index 3: global_var in scope 1 -> 100 (from scope 0)
    REQUIRE(result.reference_results[3].has_value());
    REQUIRE(result.reference_results[3]->type_id == 100);

    // Index 4: local_var in scope 1 -> 200
    REQUIRE(result.reference_results[4].has_value());
    REQUIRE(result.reference_results[4]->type_id == 200);

    // Index 5: count in scope 2 -> 3 (shadowed)
    REQUIRE(result.reference_results[5].has_value());
    REQUIRE(result.reference_results[5]->type_id == 3);

    // Index 6: local_var in scope 2 -> 200 (from scope 1)
    REQUIRE(result.reference_results[6].has_value());
    REQUIRE(result.reference_results[6]->type_id == 200);

    // Index 7: global_var in scope 2 -> 100 (from scope 0)
    REQUIRE(result.reference_results[7].has_value());
    REQUIRE(result.reference_results[7]->type_id == 100);

    // Index 8: count in scope 1 after exit 2 -> 2
    REQUIRE(result.reference_results[8].has_value());
    REQUIRE(result.reference_results[8]->type_id == 2);

    // Index 9: count in scope 0 after exit 1 -> 1
    REQUIRE(result.reference_results[9].has_value());
    REQUIRE(result.reference_results[9]->type_id == 1);

    // Index 10: local_var in scope 0 -> nullopt (closed scope)
    REQUIRE_FALSE(result.reference_results[10].has_value());

    // Index 11: unknown_symbol -> nullopt
    REQUIRE_FALSE(result.reference_results[11].has_value());
}

TEST_CASE("Deterministic Replay - Identical Logical Results Across Repeated Runs", "[trace_system]") {
    std::string filepath = "workloads/traces/sample_lexical.trace";
    auto commands = TraceParser::parseFile(filepath);

    TraceOracle oracle;
    auto run1 = TraceExecutor::execute(commands, oracle);

    oracle.reset();
    auto run2 = TraceExecutor::execute(commands, oracle);

    REQUIRE(run1.matchesLogicalResults(run2));
    REQUIRE(run1.total_commands == run2.total_commands);
    REQUIRE(run1.reference_count == run2.reference_count);
    REQUIRE(run1.successful_references == run2.successful_references);
    REQUIRE(run1.failed_references == run2.failed_references);
}

TEST_CASE("Multi-Algorithm Agreement on Flat Traces", "[trace_system]") {
    std::string flat_trace =
        "ENTER_SCOPE 0\n"
        "DECLARE var_a 10 0\n"
        "DECLARE var_b 20 0\n"
        "DECLARE var_c 30 0\n"
        "REFERENCE var_a 0\n"
        "REFERENCE var_b 0\n"
        "REFERENCE var_missing 0\n"
        "DECLARE var_d 40 0\n"
        "REFERENCE var_d 0\n"
        "REFERENCE var_c 0\n"
        "EXIT_SCOPE 0\n";

    auto commands = TraceParser::parseString(flat_trace);

    ChainingHashTable chaining_table(16);
    CuckooHashTable cuckoo_table(16);
    HopscotchHashTable hopscotch_table(32);
    SvcHashTable svc_table(16);
    TraceOracle oracle;

    auto res_chaining = TraceExecutor::execute(commands, chaining_table);
    auto res_cuckoo = TraceExecutor::execute(commands, cuckoo_table);
    auto res_hopscotch = TraceExecutor::execute(commands, hopscotch_table);
    auto res_svc = TraceExecutor::execute(commands, svc_table);
    auto res_oracle = TraceExecutor::execute(commands, oracle);

    // All 5 implementations must agree 100% on logical reference outcomes
    REQUIRE(res_chaining.matchesLogicalResults(res_oracle));
    REQUIRE(res_cuckoo.matchesLogicalResults(res_oracle));
    REQUIRE(res_hopscotch.matchesLogicalResults(res_oracle));
    REQUIRE(res_svc.matchesLogicalResults(res_oracle));
}

TEST_CASE("Scoped Trace Agreement - SVC-Hash vs Oracle", "[trace_system]") {
    std::string filepath = "workloads/traces/sample_lexical.trace";
    auto commands = TraceParser::parseFile(filepath);

    SvcHashTable svc_table(16);
    TraceOracle oracle;

    auto res_svc = TraceExecutor::execute(commands, svc_table);
    auto res_oracle = TraceExecutor::execute(commands, oracle);

    REQUIRE(res_svc.matchesLogicalResults(res_oracle));
    REQUIRE(res_svc.successful_references == 10);
    REQUIRE(res_svc.failed_references == 2);
}
