cmake_minimum_required(VERSION 3.16)
project(pq_server VERSION 1.0.0 LANGUAGES CXX)

# ==============================================================================
# Build Options
# ==============================================================================

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic")
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -DDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

# Optional: Enable SIMD optimizations
option(ENABLE_SIMD "Enable SIMD optimizations" ON)
if(ENABLE_SIMD)
    include(CheckCXXCompilerFlag)

    # Check for AVX2
    check_cxx_compiler_flag("-mavx2" COMPILER_SUPPORTS_AVX2)
    if(COMPILER_SUPPORTS_AVX2)
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mavx2")
        message(STATUS "AVX2 support enabled")
    endif()

    # Check for AVX-512
    check_cxx_compiler_flag("-mavx512f" COMPILER_SUPPORTS_AVX512)
    if(COMPILER_SUPPORTS_AVX512)
        option(ENABLE_AVX512 "Enable AVX-512 optimizations" OFF)
        if(ENABLE_AVX512)
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mavx512f")
            message(STATUS "AVX-512 support enabled")
        endif()
    endif()
endif()

# ==============================================================================
# Dependencies
# ==============================================================================

# Find required packages
find_package(Threads REQUIRED)

# Find gRPC and Protobuf
# Option 1: Using find_package (if installed via package manager)
find_package(gRPC CONFIG QUIET)
find_package(Protobuf CONFIG QUIET)

if(gRPC_FOUND AND Protobuf_FOUND)
    message(STATUS "Found gRPC via find_package")
    set(GRPC_LIBRARIES gRPC::grpc++ gRPC::grpc)
    set(PROTOBUF_LIBRARIES protobuf::libprotobuf)
else()
    # Option 2: Using pkg-config (fallback)
    find_package(PkgConfig REQUIRED)

    pkg_check_modules(GRPC REQUIRED grpc++)
    pkg_check_modules(PROTOBUF REQUIRED protobuf)

    set(GRPC_LIBRARIES ${GRPC_LIBRARIES})
    set(PROTOBUF_LIBRARIES ${PROTOBUF_LIBRARIES})

    include_directories(${GRPC_INCLUDE_DIRS} ${PROTOBUF_INCLUDE_DIRS})
    link_directories(${GRPC_LIBRARY_DIRS} ${PROTOBUF_LIBRARY_DIRS})
endif()

# Find protoc and grpc_cpp_plugin
find_program(PROTOC protoc REQUIRED)
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin REQUIRED)

message(STATUS "protoc found: ${PROTOC}")
message(STATUS "grpc_cpp_plugin found: ${GRPC_CPP_PLUGIN}")

# ==============================================================================
# Proto File Compilation
# ==============================================================================

# Proto file directory
set(PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
set(PROTO_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")

# Create output directory
file(MAKE_DIRECTORY ${PROTO_GENERATED_DIR})

# List of proto files
set(PROTO_FILES
    ${PROTO_DIR}/pq.proto
    ${PROTO_DIR}/node.proto
)

# Generated source files
set(PROTO_SRCS)
set(PROTO_HDRS)
set(GRPC_SRCS)
set(GRPC_HDRS)

# Custom command to generate protobuf and gRPC code
foreach(PROTO_FILE ${PROTO_FILES})
    get_filename_component(PROTO_NAME ${PROTO_FILE} NAME_WE)

    set(PROTO_SRC "${PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.cc")
    set(PROTO_HDR "${PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.h")
    set(GRPC_SRC "${PROTO_GENERATED_DIR}/${PROTO_NAME}.grpc.pb.cc")
    set(GRPC_HDR "${PROTO_GENERATED_DIR}/${PROTO_NAME}.grpc.pb.h")

    list(APPEND PROTO_SRCS ${PROTO_SRC})
    list(APPEND PROTO_HDRS ${PROTO_HDR})
    list(APPEND GRPC_SRCS ${GRPC_SRC})
    list(APPEND GRPC_HDRS ${GRPC_HDR})

    add_custom_command(
        OUTPUT ${PROTO_SRC} ${PROTO_HDR} ${GRPC_SRC} ${GRPC_HDR}
        COMMAND ${PROTOC}
            --proto_path=${PROTO_DIR}
            --cpp_out=${PROTO_GENERATED_DIR}
            --grpc_out=${PROTO_GENERATED_DIR}
            --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
            ${PROTO_FILE}
        DEPENDS ${PROTO_FILE}
        COMMENT "Generating C++ code from ${PROTO_FILE}"
        VERBATIM
    )
endforeach()

# Create a library for generated proto files
add_library(pq_proto STATIC
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

target_include_directories(pq_proto PUBLIC ${PROTO_GENERATED_DIR})
target_link_libraries(pq_proto PUBLIC
    ${GRPC_LIBRARIES}
    ${PROTOBUF_LIBRARIES}
)

# ==============================================================================
# Main Server Executable
# ==============================================================================

add_executable(pq_server
    server.cpp
)

target_include_directories(pq_server PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${PROTO_GENERATED_DIR}
)

target_link_libraries(pq_server PRIVATE
    pq_proto
    ${GRPC_LIBRARIES}
    ${PROTOBUF_LIBRARIES}
    Threads::Threads
)

# ==============================================================================
# Additional Tools (Optional)
# ==============================================================================

# Uncomment to build additional tools

# Encoder tool - for offline encoding of vectors
# add_executable(pq_encoder
#     tools/encoder.cpp
# )
#
# target_include_directories(pq_encoder PRIVATE
#     ${CMAKE_CURRENT_SOURCE_DIR}
#     ${PROTO_GENERATED_DIR}
# )
#
# target_link_libraries(pq_encoder PRIVATE
#     pq_proto
#     ${GRPC_LIBRARIES}
#     ${PROTOBUF_LIBRARIES}
#     Threads::Threads
# )

# Codebook analyzer tool
# add_executable(codebook_analyzer
#     tools/codebook_analyzer.cpp
# )
#
# target_include_directories(codebook_analyzer PRIVATE
#     ${CMAKE_CURRENT_SOURCE_DIR}
#     ${PROTO_GENERATED_DIR}
# )
#
# target_link_libraries(codebook_analyzer PRIVATE
#     pq_proto
#     ${GRPC_LIBRARIES}
#     ${PROTOBUF_LIBRARIES}
#     Threads::Threads
# )

# ==============================================================================
# Installation
# ==============================================================================

install(TARGETS pq_server
    RUNTIME DESTINATION bin
)

# ==============================================================================
# Testing (Optional)
# ==============================================================================

option(BUILD_TESTS "Build unit tests" OFF)

if(BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)

    add_executable(pq_tests
        tests/pq_tests.cpp
    )

    target_include_directories(pq_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${PROTO_GENERATED_DIR}
    )

    target_link_libraries(pq_tests PRIVATE
        pq_proto
        ${GRPC_LIBRARIES}
        ${PROTOBUF_LIBRARIES}
        GTest::gtest
        GTest::gtest_main
        Threads::Threads
    )

    add_test(NAME PQTests COMMAND pq_tests)

    # Additional test for quantization error
    add_executable(quantization_error_test
        tests/quantization_error_test.cpp
    )

    target_include_directories(quantization_error_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${PROTO_GENERATED_DIR}
    )

    target_link_libraries(quantization_error_test PRIVATE
        pq_proto
        ${GRPC_LIBRARIES}
        ${PROTOBUF_LIBRARIES}
        GTest::gtest
        GTest::gtest_main
        Threads::Threads
    )

    add_test(NAME QuantizationErrorTest COMMAND quantization_error_test)
endif()

# ==============================================================================
# Benchmarking (Optional)
# ==============================================================================

option(BUILD_BENCHMARKS "Build benchmarks" OFF)

if(BUILD_BENCHMARKS)
    find_package(benchmark QUIET)

    if(benchmark_FOUND)
        # Encoding benchmark
        add_executable(encoding_benchmark
            benchmarks/encoding_benchmark.cpp
        )

        target_include_directories(encoding_benchmark PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${PROTO_GENERATED_DIR}
        )

        target_link_libraries(encoding_benchmark PRIVATE
            pq_proto
            ${GRPC_LIBRARIES}
            ${PROTOBUF_LIBRARIES}
            benchmark::benchmark
            Threads::Threads
        )

        # Search benchmark
        add_executable(search_benchmark
            benchmarks/search_benchmark.cpp
        )

        target_include_directories(search_benchmark PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${PROTO_GENERATED_DIR}
        )

        target_link_libraries(search_benchmark PRIVATE
            pq_proto
            ${GRPC_LIBRARIES}
            ${PROTOBUF_LIBRARIES}
            benchmark::benchmark
            Threads::Threads
        )

        # Distance table benchmark
        add_executable(distance_table_benchmark
            benchmarks/distance_table_benchmark.cpp
        )

        target_include_directories(distance_table_benchmark PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${PROTO_GENERATED_DIR}
        )

        target_link_libraries(distance_table_benchmark PRIVATE
            pq_proto
            ${GRPC_LIBRARIES}
            ${PROTOBUF_LIBRARIES}
            benchmark::benchmark
            Threads::Threads
        )
    else()
        message(WARNING "Google Benchmark not found, skipping benchmarks")
    endif()
endif()

# ==============================================================================
# Documentation
# ==============================================================================

# Usage instructions
message(STATUS "")
message(STATUS "PQ Server Build Configuration")
message(STATUS "=============================")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "SIMD enabled: ${ENABLE_SIMD}")
message(STATUS "")
message(STATUS "To build:")
message(STATUS "  mkdir build && cd build")
message(STATUS "  cmake ..")
message(STATUS "  make -j$(nproc)")
message(STATUS "")
message(STATUS "To run:")
message(STATUS "  ./pq_server --node-id node-1 --port 50051 -m 8 -k 256")
message(STATUS "")
message(STATUS "Configuration options:")
message(STATUS "  -m: Number of subquantizers (default: 8)")
message(STATUS "  -k: Centroids per subquantizer (default: 256)")
message(STATUS "  --dimension: Vector dimension (must be divisible by -m)")
message(STATUS "")
