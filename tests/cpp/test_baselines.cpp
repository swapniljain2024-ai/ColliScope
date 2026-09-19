#include "third_party/catch2/catch.hpp"
#include "chaining_table.hpp"
#include "cuckoo_table.hpp"
#include "hopscotch_table.hpp"
#include "svc_hash/svc_hash_table.hpp"
#include <vector>
#include <memory>
#include <string>

using namespace colliscope;

TEST_CASE("Separate Chaining Baseline - Basic Operations & Metrics", "[chaining]") {
    ChainingHashTable table(8);

    REQUIRE(table.getAlgorithmName() == "chaining");
    REQUIRE(table.getElementCount() == 0);

    SymbolValue v1{1, 10, "int_var"};
    SymbolValue v2{2, 20, "float_var"};

    REQUIRE(table.insert("foo", v1, 0));
    REQUIRE(table.insert("bar", v2, 0));
    REQUIRE(table.getElementCount() == 2);

    auto res1 = table.lookup("foo", 0);
    REQUIRE(res1.has_value());
    REQUIRE(res1.value() == v1);

    auto res2 = table.lookup("bar", 0);
    REQUIRE(res2.has_value());
    REQUIRE(res2.value() == v2);

    auto res3 = table.lookup("non_existent", 0);
    REQUIRE_FALSE(res3.has_value());

    // Update existing key
    SymbolValue v1_updated{1, 15, "int_var_updated"};
    REQUIRE(table.insert("foo", v1_updated, 0));
    REQUIRE(table.getElementCount() == 2);
    REQUIRE(table.lookup("foo", 0).value() == v1_updated);

    // Test enterScope / exitScope no-ops
    table.enterScope(1, 0);
    table.exitScope(1);

    TableMetrics metrics = table.getMetrics();
    REQUIRE(metrics.algorithm_name == "chaining");
    REQUIRE(metrics.num_elements == 2);
    REQUIRE(metrics.successful_lookups == 3);
    REQUIRE(metrics.failed_lookups == 1);
    REQUIRE(metrics.custom_metrics.count("chain_length_max") > 0);
    REQUIRE(metrics.custom_metrics.count("chain_length_avg") > 0);
    REQUIRE(metrics.custom_metrics.count("key_comparisons") > 0);
    REQUIRE(metrics.custom_metrics.count("traversal_length") > 0);

    table.reset();
    REQUIRE(table.getElementCount() == 0);
    REQUIRE_FALSE(table.lookup("foo", 0).has_value());
}

TEST_CASE("Separate Chaining Baseline - Heavy Insertion & Rehash", "[chaining]") {
    ChainingHashTable table(4);

    for (int i = 0; i < 200; ++i) {
        std::string key = "var_" + std::to_string(i);
        SymbolValue val{static_cast<int64_t>(i), static_cast<uint32_t>(i), "type"};
        REQUIRE(table.insert(key, val, 0));
    }

    REQUIRE(table.getElementCount() == 200);
    REQUIRE(table.getBucketCount() >= 200); // Rehashed automatically

    for (int i = 0; i < 200; ++i) {
        std::string key = "var_" + std::to_string(i);
        auto res = table.lookup(key, 0);
        REQUIRE(res.has_value());
        REQUIRE(res.value().type_id == i);
    }
}

TEST_CASE("Plain Cuckoo Baseline - Basic Operations, Kicks & Rehashes", "[cuckoo]") {
    CuckooHashTable table(16);

    REQUIRE(table.getAlgorithmName() == "cuckoo");
    REQUIRE(table.getElementCount() == 0);

    SymbolValue v1{100, 1, "x"};
    SymbolValue v2{200, 2, "y"};

    REQUIRE(table.insert("x", v1, 0));
    REQUIRE(table.insert("y", v2, 0));
    REQUIRE(table.getElementCount() == 2);

    REQUIRE(table.lookup("x", 0).value() == v1);
    REQUIRE(table.lookup("y", 0).value() == v2);
    REQUIRE_FALSE(table.lookup("z", 0).has_value());

    // Force many insertions to trigger cuckoo evictions/kicks and rehash
    for (int i = 0; i < 150; ++i) {
        std::string key = "cuckoo_key_" + std::to_string(i);
        SymbolValue val{static_cast<int64_t>(i), 10, "meta"};
        REQUIRE(table.insert(key, val, 0));
    }

    REQUIRE(table.getElementCount() == 152);

    for (int i = 0; i < 150; ++i) {
        std::string key = "cuckoo_key_" + std::to_string(i);
        auto res = table.lookup(key, 0);
        REQUIRE(res.has_value());
        REQUIRE(res.value().type_id == i);
    }

    TableMetrics m = table.getMetrics();
    REQUIRE(m.algorithm_name == "cuckoo");
    REQUIRE(m.num_elements == 152);
    REQUIRE(m.custom_metrics.count("relocations_kicks") > 0);
    REQUIRE(m.custom_metrics.count("rehashes") > 0);
    REQUIRE(m.custom_metrics.count("max_displacement") > 0);
}

TEST_CASE("Hopscotch Baseline - Basic Operations & Neighborhood Movements", "[hopscotch]") {
    HopscotchHashTable table(32);

    REQUIRE(table.getAlgorithmName() == "hopscotch");
    REQUIRE(table.getElementCount() == 0);

    SymbolValue v1{10, 1, "a"};
    SymbolValue v2{20, 2, "b"};

    REQUIRE(table.insert("alpha", v1, 0));
    REQUIRE(table.insert("beta", v2, 0));
    REQUIRE(table.getElementCount() == 2);

    REQUIRE(table.lookup("alpha", 0).value() == v1);
    REQUIRE(table.lookup("beta", 0).value() == v2);
    REQUIRE_FALSE(table.lookup("gamma", 0).has_value());

    // Insert 100 elements to force neighborhood movements and potential rehashes
    for (int i = 0; i < 100; ++i) {
        std::string key = "hop_key_" + std::to_string(i);
        SymbolValue val{static_cast<int64_t>(i), 50, "val"};
        REQUIRE(table.insert(key, val, 0));
    }

    REQUIRE(table.getElementCount() == 102);

    for (int i = 0; i < 100; ++i) {
        std::string key = "hop_key_" + std::to_string(i);
        auto res = table.lookup(key, 0);
        REQUIRE(res.has_value());
        REQUIRE(res.value().type_id == i);
    }

    TableMetrics m = table.getMetrics();
    REQUIRE(m.algorithm_name == "hopscotch");
    REQUIRE(m.num_elements == 102);
    REQUIRE(m.custom_metrics.count("neighbourhood_movements") > 0);
    REQUIRE(m.custom_metrics.count("key_comparisons") > 0);
}

TEST_CASE("Polymorphic ISymbolTable Baseline Suite", "[polymorphic]") {
    std::vector<std::unique_ptr<ISymbolTable>> tables;
    tables.push_back(std::make_unique<ChainingHashTable>(16));
    tables.push_back(std::make_unique<CuckooHashTable>(16));
    tables.push_back(std::make_unique<HopscotchHashTable>(32));
    tables.push_back(std::make_unique<SvcHashTable>(16));

    for (auto& table : tables) {
        INFO("Testing algorithm: " << table->getAlgorithmName());

        table->reset();
        table->enterScope(0, 0);

        for (int i = 0; i < 50; ++i) {
            std::string key = "sym_" + std::to_string(i);
            SymbolValue val{static_cast<int64_t>(i), static_cast<uint32_t>(i), "type"};
            REQUIRE(table->insert(key, val, 0));
        }

        for (int i = 0; i < 50; ++i) {
            std::string key = "sym_" + std::to_string(i);
            auto res = table->lookup(key, 0);
            REQUIRE(res.has_value());
            REQUIRE(res.value().type_id == i);
        }

        TableMetrics m = table->getMetrics();
        REQUIRE(m.num_elements == 50);
        REQUIRE(m.successful_lookups == 50);
        REQUIRE(m.algorithm_name == table->getAlgorithmName());
    }
}
