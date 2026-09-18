# tests/CMakeLists.txt - Test targets

add_executable(test_scaffolding
    cpp/test_scaffolding.cpp
)

target_link_libraries(test_scaffolding PRIVATE colliscope_interface)

add_test(NAME TestScaffolding COMMAND test_scaffolding)
