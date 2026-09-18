#pragma once

#include <string>
#include <vector>
#include <stdexcept>
#include <fstream>
#include <cmath>
#include "third_party/json.hpp"

namespace colliscope {

enum class IdentifierDimension {
    Random,
    RealSource,
    FrequencyMatched
};

enum class ScopeDimension {
    Flat,
    Nested
};

enum class WorkloadType {
    DeclarationHeavy,
    LookupHeavy,
    Mixed
};

inline std::string toString(IdentifierDimension dim) {
    switch (dim) {
        case IdentifierDimension::Random: return "random";
        case IdentifierDimension::RealSource: return "real-source";
        case IdentifierDimension::FrequencyMatched: return "frequency-matched";
    }
    return "random";
}

inline IdentifierDimension parseIdentifierDimension(const std::string& s) {
    if (s == "random") return IdentifierDimension::Random;
    if (s == "real-source") return IdentifierDimension::RealSource;
    if (s == "frequency-matched") return IdentifierDimension::FrequencyMatched;
    throw std::invalid_argument("Invalid identifier dimension: '" + s + "'");
}

inline std::string toString(ScopeDimension dim) {
    switch (dim) {
        case ScopeDimension::Flat: return "flat";
        case ScopeDimension::Nested: return "nested";
    }
    return "flat";
}

inline ScopeDimension parseScopeDimension(const std::string& s) {
    if (s == "flat") return ScopeDimension::Flat;
    if (s == "nested") return ScopeDimension::Nested;
    throw std::invalid_argument("Invalid scope dimension: '" + s + "'");
}

inline std::string toString(WorkloadType type) {
    switch (type) {
        case WorkloadType::DeclarationHeavy: return "declaration-heavy";
        case WorkloadType::LookupHeavy: return "lookup-heavy";
        case WorkloadType::Mixed: return "mixed";
    }
    return "mixed";
}

inline WorkloadType parseWorkloadType(const std::string& s) {
    if (s == "declaration-heavy") return WorkloadType::DeclarationHeavy;
    if (s == "lookup-heavy") return WorkloadType::LookupHeavy;
    if (s == "mixed") return WorkloadType::Mixed;
    throw std::invalid_argument("Invalid workload type: '" + s + "'");
}

struct OperationMix {
    double insert_ratio{0.4};
    double lookup_ratio{0.5};
    double scope_ratio{0.1};

    void validate() const {
        if (insert_ratio < 0.0 || lookup_ratio < 0.0 || scope_ratio < 0.0) {
            throw std::invalid_argument("Operation mix ratios must be non-negative");
        }
        double sum = insert_ratio + lookup_ratio + scope_ratio;
        if (std::abs(sum - 1.0) > 1e-4) {
            throw std::invalid_argument("Operation mix ratios must sum to 1.0 (got " + std::to_string(sum) + ")");
        }
    }
};

struct BenchmarkConfig {
    IdentifierDimension identifier_dimension{IdentifierDimension::Random};
    ScopeDimension scope_dimension{ScopeDimension::Flat};
    WorkloadType workload_type{WorkloadType::Mixed};
    double load_factor{0.70};
    OperationMix operation_mix;
    std::vector<std::string> algorithms{"chaining", "cuckoo", "hopscotch", "svc_hash"};
    uint32_t repetitions{30};
    uint64_t num_operations{10000};
    uint32_t max_scope_depth{8};

    void validate() const {
        if (load_factor <= 0.0 || load_factor > 1.0) {
            throw std::invalid_argument("Load factor must be in range (0.0, 1.0], got " + std::to_string(load_factor));
        }
        if (repetitions == 0) {
            throw std::invalid_argument("Repetitions must be at least 1");
        }
        if (num_operations == 0) {
            throw std::invalid_argument("Number of operations must be greater than 0");
        }
        if (algorithms.empty()) {
            throw std::invalid_argument("At least one algorithm must be specified");
        }
        for (const auto& algo : algorithms) {
            if (algo != "chaining" && algo != "cuckoo" && algo != "hopscotch" && algo != "svc_hash" && algo != "coalesced") {
                throw std::invalid_argument("Unsupported algorithm: '" + algo + "'");
            }
        }
        operation_mix.validate();
    }

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["identifier_dimension"] = toString(identifier_dimension);
        j["scope_dimension"] = toString(scope_dimension);
        j["workload_type"] = toString(workload_type);
        j["load_factor"] = load_factor;
        j["operation_mix"] = {
            {"insert_ratio", operation_mix.insert_ratio},
            {"lookup_ratio", operation_mix.lookup_ratio},
            {"scope_ratio", operation_mix.scope_ratio}
        };
        j["algorithms"] = algorithms;
        j["repetitions"] = repetitions;
        j["num_operations"] = num_operations;
        j["max_scope_depth"] = max_scope_depth;
        return j;
    }

    static BenchmarkConfig fromJson(const nlohmann::json& j) {
        BenchmarkConfig cfg;
        if (!j.contains("identifier_dimension") ||
            !j.contains("scope_dimension") ||
            !j.contains("workload_type") ||
            !j.contains("load_factor")) {
            throw std::invalid_argument("Configuration is missing required fields");
        }

        cfg.identifier_dimension = parseIdentifierDimension(j["identifier_dimension"].get<std::string>());
        cfg.scope_dimension = parseScopeDimension(j["scope_dimension"].get<std::string>());
        cfg.workload_type = parseWorkloadType(j["workload_type"].get<std::string>());
        cfg.load_factor = j["load_factor"].get<double>();

        if (j.contains("operation_mix")) {
            const auto& om = j["operation_mix"];
            if (om.contains("insert_ratio")) cfg.operation_mix.insert_ratio = om["insert_ratio"].get<double>();
            if (om.contains("lookup_ratio")) cfg.operation_mix.lookup_ratio = om["lookup_ratio"].get<double>();
            if (om.contains("scope_ratio")) cfg.operation_mix.scope_ratio = om["scope_ratio"].get<double>();
        }

        if (j.contains("algorithms")) {
            cfg.algorithms = j["algorithms"].get<std::vector<std::string>>();
        }

        if (j.contains("repetitions")) {
            cfg.repetitions = j["repetitions"].get<uint32_t>();
        }

        if (j.contains("num_operations")) {
            cfg.num_operations = j["num_operations"].get<uint64_t>();
        }

        if (j.contains("max_scope_depth")) {
            cfg.max_scope_depth = j["max_scope_depth"].get<uint32_t>();
        }

        cfg.validate();
        return cfg;
    }

    static BenchmarkConfig fromJsonFile(const std::string& filepath) {
        std::ifstream file(filepath);
        if (!file.is_open()) {
            throw std::runtime_error("Could not open configuration file: " + filepath);
        }
        nlohmann::json j;
        file >> j;
        return fromJson(j);
    }
};

} // namespace colliscope
