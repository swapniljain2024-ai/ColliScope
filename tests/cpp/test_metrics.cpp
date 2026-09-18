#include "third_party/catch2/catch.hpp"
#include "common/metrics.hpp"

using namespace colliscope;

TEST_CASE("TableMetrics JSON serialization roundtrip", "[metrics]") {
    TableMetrics m;
    m.algorithm_name = "svc_hash";
    m.num_elements = 5000;
    m.capacity = 8192;
    m.load_factor = 5000.0 / 8192.0;
    m.insertion_time_ns = 1250000;
    m.lookup_time_ns = 3400000;
    m.scope_exit_time_ns = 45000;
    m.total_operations = 15000;
    m.throughput_ops_sec = 15000.0 / ((1250000 + 3400000) * 1e-9);
    m.memory_usage_bytes = 131072;
    m.collision_count = 320;
    m.successful_lookups = 8000;
    m.failed_lookups = 2000;

    m.custom_metrics["candidate_locations_examined"] = 16000.0;
    m.custom_metrics["scope_checks_count"] = 9500.0;
    m.custom_metrics["stash_usage"] = 2.0;

    nlohmann::json j = m.toJson();
    TableMetrics deserialized = TableMetrics::fromJson(j);

    REQUIRE(deserialized.algorithm_name == "svc_hash");
    REQUIRE(deserialized.num_elements == 5000);
    REQUIRE(deserialized.capacity == 8192);
    REQUIRE(deserialized.load_factor == Approx(m.load_factor));
    REQUIRE(deserialized.insertion_time_ns == 1250000);
    REQUIRE(deserialized.lookup_time_ns == 3400000);
    REQUIRE(deserialized.scope_exit_time_ns == 45000);
    REQUIRE(deserialized.total_operations == 15000);
    REQUIRE(deserialized.throughput_ops_sec == Approx(m.throughput_ops_sec));
    REQUIRE(deserialized.memory_usage_bytes == 131072);
    REQUIRE(deserialized.collision_count == 320);
    REQUIRE(deserialized.successful_lookups == 8000);
    REQUIRE(deserialized.failed_lookups == 2000);
    REQUIRE(deserialized.custom_metrics.at("candidate_locations_examined") == 16000.0);
    REQUIRE(deserialized.custom_metrics.at("stash_usage") == 2.0);
}

TEST_CASE("TableMetrics CSV serialization", "[metrics]") {
    TableMetrics m;
    m.algorithm_name = "chaining";
    m.num_elements = 100;
    m.capacity = 256;
    m.load_factor = 0.390625;
    m.insertion_time_ns = 50000;
    m.lookup_time_ns = 120000;
    m.scope_exit_time_ns = 0;
    m.total_operations = 300;
    m.throughput_ops_sec = 1764705.88;
    m.memory_usage_bytes = 4096;
    m.collision_count = 18;
    m.successful_lookups = 150;
    m.failed_lookups = 50;

    std::string header = TableMetrics::toCsvHeader();
    std::string row = m.toCsvRow();

    REQUIRE(header.find("algorithm_name") != std::string::npos);
    REQUIRE(header.find("collision_count") != std::string::npos);
    REQUIRE(row.find("chaining") != std::string::npos);
    REQUIRE(row.find("1764705.88") != std::string::npos);
}
