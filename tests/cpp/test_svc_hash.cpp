#include "third_party/catch2/catch.hpp"
#include "svc_hash/svc_hash_table.hpp"
#include <random>
#include <unordered_map>
#include <vector>
#include <string>
#include <memory>
#include <iostream>

using namespace colliscope;

// Reference Oracle Implementation for Scoped Symbol Table
class NaiveScopedSymbolTable {
public:
    struct ScopeNode {
        uint32_t scope_id;
        uint32_t parent_id;
        bool active{true};
        std::unordered_map<std::string, SymbolValue> symbols;
    };

    NaiveScopedSymbolTable() {
        reset();
    }

    void reset() {
        scopes_.clear();
        stack_.clear();
        scopes_[0] = ScopeNode{0, 0, true, {}};
        stack_.push_back(0);
        current_scope_id_ = 0;
    }

    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) {
        if (scopes_.empty()) {
            scopes_[0] = ScopeNode{0, 0, true, {}};
            stack_.push_back(0);
            current_scope_id_ = 0;
        }

        if (scope_id == 0 && parent_scope_id == 0 && scopes_.count(0) && scopes_[0].active) {
            return;
        }

        if (!scopes_.count(parent_scope_id) || !scopes_[parent_scope_id].active) {
            throw std::invalid_argument("Oracle: parent scope not active");
        }
        if (parent_scope_id != current_scope_id_) {
            throw std::invalid_argument("Oracle: parent scope not current scope");
        }
        if (scopes_.count(scope_id) && scopes_[scope_id].active) {
            throw std::invalid_argument("Oracle: scope already active");
        }

        scopes_[scope_id] = ScopeNode{scope_id, parent_scope_id, true, {}};
        stack_.push_back(scope_id);
        current_scope_id_ = scope_id;
    }

    void exitScope(uint32_t scope_id) {
        if (scope_id != current_scope_id_ || !scopes_.count(scope_id) || !scopes_[scope_id].active) {
            throw std::invalid_argument("Oracle: invalid exitScope");
        }
        scopes_[scope_id].active = false;
        if (!stack_.empty() && stack_.back() == scope_id) {
            stack_.pop_back();
        }
        current_scope_id_ = stack_.empty() ? 0 : stack_.back();
    }

    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
        if (!scopes_.count(scope_id) || !scopes_[scope_id].active) {
            return false;
        }
        if (scopes_[scope_id].symbols.count(key)) {
            return false; // Duplicate in same scope rejected
        }
        scopes_[scope_id].symbols[key] = value;
        return true;
    }

    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) {
        uint32_t curr = scope_id;
        while (true) {
            if (!scopes_.count(curr) || !scopes_[curr].active) {
                break;
            }
            auto it = scopes_[curr].symbols.find(key);
            if (it != scopes_[curr].symbols.end()) {
                return it->second;
            }
            if (curr == 0 || scopes_[curr].parent_id == curr) {
                break;
            }
            curr = scopes_[curr].parent_id;
        }
        return std::nullopt;
    }

    uint32_t getCurrentScopeId() const { return current_scope_id_; }

private:
    std::unordered_map<uint32_t, ScopeNode> scopes_;
    std::vector<uint32_t> stack_;
    uint32_t current_scope_id_{0};
};


TEST_CASE("SVC-Hash Basic Operations and Interfaces", "[svc_hash]") {
    SvcHashTable table(16);

    REQUIRE(table.getAlgorithmName() == "svc_hash");
    REQUIRE(table.getBucketCount() == 16);
    REQUIRE(table.getCurrentScopeId() == 0);
    REQUIRE(table.isScopeActive(0) == true);

    SymbolValue v1{101, 12, "var_a"};
    SymbolValue v2{102, 15, "var_b"};

    SECTION("Single key insert and lookup in global scope") {
        REQUIRE(table.insert("alpha", v1, 0) == true);
        auto res = table.lookup("alpha", 0);
        REQUIRE(res.has_value());
        REQUIRE(res.value() == v1);

        auto missing = table.lookup("beta", 0);
        REQUIRE(!missing.has_value());
    }

    SECTION("Duplicate insertion in same scope is rejected") {
        REQUIRE(table.insert("alpha", v1, 0) == true);
        REQUIRE(table.insert("alpha", v2, 0) == false); // Duplicate contract
        auto res = table.lookup("alpha", 0);
        REQUIRE(res.has_value());
        REQUIRE(res.value() == v1);
    }

    SECTION("Reset clears contents and restores scope 0") {
        table.insert("alpha", v1, 0);
        table.reset();
        REQUIRE(table.lookup("alpha", 0) == std::nullopt);
        REQUIRE(table.getCurrentScopeId() == 0);
        REQUIRE(table.isScopeActive(0) == true);
    }
}

TEST_CASE("SVC-Hash Scope Entry and Exit Contract Validation", "[svc_hash]") {
    SvcHashTable table(16);

    SECTION("Valid scope hierarchy navigation") {
        REQUIRE_NOTHROW(table.enterScope(1, 0));
        REQUIRE(table.getCurrentScopeId() == 1);
        REQUIRE_NOTHROW(table.enterScope(2, 1));
        REQUIRE(table.getCurrentScopeId() == 2);

        REQUIRE_NOTHROW(table.exitScope(2));
        REQUIRE(table.getCurrentScopeId() == 1);
        REQUIRE_NOTHROW(table.exitScope(1));
        REQUIRE(table.getCurrentScopeId() == 0);
    }

    SECTION("Reject enterScope under inactive parent") {
        table.enterScope(1, 0);
        table.exitScope(1);
        REQUIRE_THROWS_AS(table.enterScope(2, 1), std::invalid_argument);
    }

    SECTION("Reject enterScope under non-current scope") {
        table.enterScope(1, 0);
        table.enterScope(2, 1);
        // Current scope is 2; trying to enter scope 3 under parent 1 must be rejected
        REQUIRE_THROWS_AS(table.enterScope(3, 1), std::invalid_argument);
    }

    SECTION("Reject exitScope out of order") {
        table.enterScope(1, 0);
        table.enterScope(2, 1);
        // Current scope is 2; trying to exit scope 1 out of order must be rejected
        REQUIRE_THROWS_AS(table.exitScope(1), std::invalid_argument);
    }
}

TEST_CASE("SVC-Hash Lexical Scope Shadowing and Parent Walk", "[svc_hash]") {
    SvcHashTable table(16);

    SymbolValue g_val{1, 10, "global_x"};
    SymbolValue s1_val{2, 20, "scope1_x"};
    SymbolValue s2_val{3, 30, "scope2_x"};
    SymbolValue y_val{4, 40, "scope1_y"};

    table.insert("x", g_val, 0);

    table.enterScope(1, 0);
    table.insert("x", s1_val, 1);
    table.insert("y", y_val, 1);

    table.enterScope(2, 1);
    table.insert("x", s2_val, 2);

    SECTION("Shadowing resolution from innermost scope") {
        // Query "x" from scope 2 -> should return scope 2's declaration
        auto res2 = table.lookup("x", 2);
        REQUIRE(res2.has_value());
        REQUIRE(res2.value() == s2_val);

        // Query "x" from scope 1 -> should return scope 1's declaration
        auto res1 = table.lookup("x", 1);
        REQUIRE(res1.has_value());
        REQUIRE(res1.value() == s1_val);

        // Query "x" from scope 0 -> should return global scope's declaration
        auto res0 = table.lookup("x", 0);
        REQUIRE(res0.has_value());
        REQUIRE(res0.value() == g_val);
    }

    SECTION("Parent scope resolution for un-shadowed variable") {
        // Query "y" from scope 2 (declared in scope 1)
        auto res_y = table.lookup("y", 2);
        REQUIRE(res_y.has_value());
        REQUIRE(res_y.value() == y_val);
    }

    SECTION("Scope exit tombstoning makes symbols invisible") {
        table.exitScope(2); // Exit scope 2
        // Query "x" from scope 1 -> scope 2's declaration is tombstoned/inactive, returns scope 1's declaration
        auto res_after = table.lookup("x", 1);
        REQUIRE(res_after.has_value());
        REQUIRE(res_after.value() == s1_val);

        // Query "x" from scope 2 -> scope 2 is no longer active
        auto res_dead = table.lookup("x", 2);
        REQUIRE(!res_dead.has_value());
    }
}

TEST_CASE("SVC-Hash Stash Shadowing Correctness (Per-Ancestor Stash Probe)", "[svc_hash]") {
    SvcHashTable table(4); // Small table size to encourage displacement

    SymbolValue outer_val{10, 100, "outer_bucket"};
    SymbolValue inner_val{20, 200, "inner_stashed"};

    // Insert outer scope symbol
    table.insert("target", outer_val, 0);

    table.enterScope(1, 0);
    table.enterScope(2, 1);

    // Force inner scope symbol into stash or specific placement
    // Insert many dummy keys into scope 2 to force cuckoo evictions and stash usage
    for (int i = 0; i < 50; ++i) {
        SymbolValue dummy{1000 + i, static_cast<uint32_t>(i), "dummy"};
        table.insert("dummy_" + std::to_string(i), dummy, 2);
    }

    // Insert inner scope declaration for "target"
    table.insert("target", inner_val, 2);

    // Lookup "target" from scope 2 MUST return inner_val, even if inner_val ended up in stash
    // and outer_val is in a bucket for scope 0!
    auto res = table.lookup("target", 2);
    REQUIRE(res.has_value());
    REQUIRE(res.value() == inner_val);
}

TEST_CASE("SVC-Hash Evictions, Table Doubling and Compaction", "[svc_hash]") {
    SvcHashTable table(4);

    SECTION("High volume insertion triggers table growth") {
        size_t initial_buckets = table.getBucketCount();
        for (int i = 0; i < 200; ++i) {
            SymbolValue v{i, static_cast<uint32_t>(i), "val_" + std::to_string(i)};
            REQUIRE(table.insert("var_" + std::to_string(i), v, 0) == true);
        }
        REQUIRE(table.getBucketCount() > initial_buckets);
        REQUIRE(table.getOccupiedCount() == 200);

        // Verify all 200 items look up correctly
        for (int i = 0; i < 200; ++i) {
            auto res = table.lookup("var_" + std::to_string(i), 0);
            REQUIRE(res.has_value());
            REQUIRE(res.value().type_id == i);
        }
    }

    SECTION("Metrics tracking") {
        table.insert("m1", SymbolValue{1, 1, "m"}, 0);
        table.lookup("m1", 0);
        table.lookup("m2", 0);

        TableMetrics m = table.getMetrics();
        REQUIRE(m.algorithm_name == "svc_hash");
        REQUIRE(m.total_operations >= 3);
        REQUIRE(m.successful_lookups >= 1);
        REQUIRE(m.failed_lookups >= 1);
        REQUIRE(m.custom_metrics.count("svc_bucket_count") > 0);
    }
}

TEST_CASE("SVC-Hash Mandatory Differential Oracle Testing", "[svc_hash][oracle]") {
    SvcHashTable table(16);
    NaiveScopedSymbolTable oracle;

    std::mt19937 rng(12345); // Fixed seed for 100% deterministic reproducibility
    std::uniform_int_distribution<int> op_dist(0, 3); // 0: insert, 1: lookup, 2: enterScope, 3: exitScope

    uint32_t scope_counter = 1;
    std::vector<std::string> keys;
    for (int i = 0; i < 100; ++i) {
        keys.push_back("sym_" + std::to_string(i));
    }

    constexpr int NUM_OPERATIONS = 3000;

    for (int op = 0; op < NUM_OPERATIONS; ++op) {
        int choice = op_dist(rng);

        if (choice == 0) { // Insert
            std::string k = keys[rng() % keys.size()];
            uint32_t curr_scope = oracle.getCurrentScopeId();
            SymbolValue val{static_cast<int64_t>(op), static_cast<uint32_t>(op), "meta_" + std::to_string(op)};

            bool oracle_res = oracle.insert(k, val, curr_scope);
            bool table_res = table.insert(k, val, curr_scope);
            REQUIRE(table_res == oracle_res);

        } else if (choice == 1) { // Lookup
            std::string k = keys[rng() % keys.size()];
            uint32_t curr_scope = oracle.getCurrentScopeId();

            auto oracle_val = oracle.lookup(k, curr_scope);
            auto table_val = table.lookup(k, curr_scope);

            REQUIRE(table_val.has_value() == oracle_val.has_value());
            if (oracle_val.has_value()) {
                REQUIRE(table_val.value() == oracle_val.value());
            }

        } else if (choice == 2) { // enterScope
            uint32_t new_scope = scope_counter++;
            uint32_t parent = oracle.getCurrentScopeId();

            oracle.enterScope(new_scope, parent);
            table.enterScope(new_scope, parent);

            REQUIRE(table.getCurrentScopeId() == oracle.getCurrentScopeId());

        } else if (choice == 3) { // exitScope
            uint32_t curr_scope = oracle.getCurrentScopeId();
            if (curr_scope != 0) { // Cannot exit root scope
                oracle.exitScope(curr_scope);
                table.exitScope(curr_scope);

                REQUIRE(table.getCurrentScopeId() == oracle.getCurrentScopeId());
            }
        }
    }
}
