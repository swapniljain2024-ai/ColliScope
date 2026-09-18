#include "third_party/catch2/catch.hpp"
#include "common/config.hpp"

using namespace colliscope;

TEST_CASE("BenchmarkConfig valid JSON parsing", "[config]") {
    nlohmann::json valid_json = {
        {"identifier_dimension", "real-source"},
        {"scope_dimension", "nested"},
        {"workload_type", "lookup-heavy"},
        {"load_factor", 0.85},
        {"operation_mix", {
            {"insert_ratio", 0.2},
            {"lookup_ratio", 0.7},
            {"scope_ratio", 0.1}
        }},
        {"algorithms", {"chaining", "svc_hash"}},
        {"repetitions", 15},
        {"num_operations", 50000},
        {"max_scope_depth", 16}
    };

    BenchmarkConfig cfg = BenchmarkConfig::fromJson(valid_json);
    REQUIRE(cfg.identifier_dimension == IdentifierDimension::RealSource);
    REQUIRE(cfg.scope_dimension == ScopeDimension::Nested);
    REQUIRE(cfg.workload_type == WorkloadType::LookupHeavy);
    REQUIRE(cfg.load_factor == Approx(0.85));
    REQUIRE(cfg.algorithms.size() == 2);
    REQUIRE(cfg.algorithms[0] == "chaining");
    REQUIRE(cfg.algorithms[1] == "svc_hash");
    REQUIRE(cfg.repetitions == 15);
    REQUIRE(cfg.num_operations == 50000);
    REQUIRE(cfg.max_scope_depth == 16);

    // Test roundtrip serialization
    nlohmann::json roundtrip = cfg.toJson();
    BenchmarkConfig cfg2 = BenchmarkConfig::fromJson(roundtrip);
    REQUIRE(cfg2.load_factor == Approx(cfg.load_factor));
    REQUIRE(cfg2.repetitions == cfg.repetitions);
}

TEST_CASE("BenchmarkConfig invalid missing required fields", "[config]") {
    nlohmann::json missing_json = {
        {"identifier_dimension", "random"},
        {"scope_dimension", "flat"}
        // missing workload_type and load_factor
    };

    REQUIRE_THROWS_AS(BenchmarkConfig::fromJson(missing_json), std::invalid_argument);
}

TEST_CASE("BenchmarkConfig invalid load factor", "[config]") {
    nlohmann::json bad_lf = {
        {"identifier_dimension", "random"},
        {"scope_dimension", "flat"},
        {"workload_type", "mixed"},
        {"load_factor", 1.5} // > 1.0 invalid
    };

    REQUIRE_THROWS_AS(BenchmarkConfig::fromJson(bad_lf), std::invalid_argument);

    bad_lf["load_factor"] = -0.1;
    REQUIRE_THROWS_AS(BenchmarkConfig::fromJson(bad_lf), std::invalid_argument);
}

TEST_CASE("BenchmarkConfig invalid operation mix", "[config]") {
    nlohmann::json bad_mix = {
        {"identifier_dimension", "random"},
        {"scope_dimension", "flat"},
        {"workload_type", "mixed"},
        {"load_factor", 0.70},
        {"operation_mix", {
            {"insert_ratio", 0.5},
            {"lookup_ratio", 0.8},
            {"scope_ratio", 0.1} // sum = 1.4 != 1.0
        }}
    };

    REQUIRE_THROWS_AS(BenchmarkConfig::fromJson(bad_mix), std::invalid_argument);
}

TEST_CASE("BenchmarkConfig invalid algorithm name", "[config]") {
    nlohmann::json bad_algo = {
        {"identifier_dimension", "random"},
        {"scope_dimension", "flat"},
        {"workload_type", "mixed"},
        {"load_factor", 0.70},
        {"algorithms", {"linear_probing"}} // Explicitly excluded algorithm!
    };

    REQUIRE_THROWS_AS(BenchmarkConfig::fromJson(bad_algo), std::invalid_argument);
}
