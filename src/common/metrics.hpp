#pragma once

#include <string>
#include <cstdint>
#include <map>
#include <sstream>
#include <iomanip>
#include "third_party/json.hpp"

namespace colliscope {

struct TableMetrics {
    std::string algorithm_name{"unknown"};
    uint64_t num_elements{0};
    uint64_t capacity{0};
    double load_factor{0.0};
    uint64_t insertion_time_ns{0};
    uint64_t lookup_time_ns{0};
    uint64_t scope_exit_time_ns{0};
    uint64_t total_operations{0};
    double throughput_ops_sec{0.0};
    uint64_t memory_usage_bytes{0};
    uint64_t collision_count{0};
    uint64_t successful_lookups{0};
    uint64_t failed_lookups{0};

    // Algorithm-specific extension metrics (e.g. chain_length_max, relocations_kicks, etc.)
    // NOTE: Internal probe/kick/chain counts are NOT directly comparable across algorithms!
    std::map<std::string, double> custom_metrics;

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["algorithm_name"] = algorithm_name;
        j["num_elements"] = num_elements;
        j["capacity"] = capacity;
        j["load_factor"] = load_factor;
        j["insertion_time_ns"] = insertion_time_ns;
        j["lookup_time_ns"] = lookup_time_ns;
        j["scope_exit_time_ns"] = scope_exit_time_ns;
        j["total_operations"] = total_operations;
        j["throughput_ops_sec"] = throughput_ops_sec;
        j["memory_usage_bytes"] = memory_usage_bytes;
        j["collision_count"] = collision_count;
        j["successful_lookups"] = successful_lookups;
        j["failed_lookups"] = failed_lookups;
        j["custom_metrics"] = custom_metrics;
        return j;
    }

    static TableMetrics fromJson(const nlohmann::json& j) {
        TableMetrics m;
        if (j.contains("algorithm_name")) m.algorithm_name = j["algorithm_name"].get<std::string>();
        if (j.contains("num_elements")) m.num_elements = j["num_elements"].get<uint64_t>();
        if (j.contains("capacity")) m.capacity = j["capacity"].get<uint64_t>();
        if (j.contains("load_factor")) m.load_factor = j["load_factor"].get<double>();
        if (j.contains("insertion_time_ns")) m.insertion_time_ns = j["insertion_time_ns"].get<uint64_t>();
        if (j.contains("lookup_time_ns")) m.lookup_time_ns = j["lookup_time_ns"].get<uint64_t>();
        if (j.contains("scope_exit_time_ns")) m.scope_exit_time_ns = j["scope_exit_time_ns"].get<uint64_t>();
        if (j.contains("total_operations")) m.total_operations = j["total_operations"].get<uint64_t>();
        if (j.contains("throughput_ops_sec")) m.throughput_ops_sec = j["throughput_ops_sec"].get<double>();
        if (j.contains("memory_usage_bytes")) m.memory_usage_bytes = j["memory_usage_bytes"].get<uint64_t>();
        if (j.contains("collision_count")) m.collision_count = j["collision_count"].get<uint64_t>();
        if (j.contains("successful_lookups")) m.successful_lookups = j["successful_lookups"].get<uint64_t>();
        if (j.contains("failed_lookups")) m.failed_lookups = j["failed_lookups"].get<uint64_t>();
        if (j.contains("custom_metrics") && j["custom_metrics"].is_object()) {
            m.custom_metrics = j["custom_metrics"].get<std::map<std::string, double>>();
        }
        return m;
    }

    static std::string toCsvHeader() {
        return "algorithm_name,num_elements,capacity,load_factor,insertion_time_ns,lookup_time_ns,"
               "scope_exit_time_ns,total_operations,throughput_ops_sec,memory_usage_bytes,"
               "collision_count,successful_lookups,failed_lookups";
    }

    std::string toCsvRow() const {
        std::ostringstream oss;
        oss << algorithm_name << ","
            << num_elements << ","
            << capacity << ","
            << std::fixed << std::setprecision(4) << load_factor << ","
            << insertion_time_ns << ","
            << lookup_time_ns << ","
            << scope_exit_time_ns << ","
            << total_operations << ","
            << std::fixed << std::setprecision(2) << throughput_ops_sec << ","
            << memory_usage_bytes << ","
            << collision_count << ","
            << successful_lookups << ","
            << failed_lookups;
        return oss.str();
    }
};

} // namespace colliscope
