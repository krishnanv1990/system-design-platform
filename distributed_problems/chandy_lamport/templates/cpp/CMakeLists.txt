cmake_minimum_required(VERSION 3.16)
project(chandy_lamport_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(Threads REQUIRED)
find_package(Protobuf CONFIG REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# Proto file
set(PROTO_PATH "${CMAKE_SOURCE_DIR}/../proto")
set(PROTO_FILE "${PROTO_PATH}/chandy_lamport.proto")

# Generated files
set(PROTO_SRCS "${CMAKE_BINARY_DIR}/chandy_lamport.pb.cc")
set(PROTO_HDRS "${CMAKE_BINARY_DIR}/chandy_lamport.pb.h")
set(GRPC_SRCS "${CMAKE_BINARY_DIR}/chandy_lamport.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_BINARY_DIR}/chandy_lamport.grpc.pb.h")

# Get the protoc and grpc_cpp_plugin executables
get_target_property(PROTOC_EXECUTABLE protobuf::protoc IMPORTED_LOCATION)
get_target_property(GRPC_CPP_PLUGIN gRPC::grpc_cpp_plugin IMPORTED_LOCATION)

# Generate proto files
add_custom_command(
    OUTPUT ${PROTO_SRCS} ${PROTO_HDRS} ${GRPC_SRCS} ${GRPC_HDRS}
    COMMAND ${PROTOC_EXECUTABLE}
    ARGS --grpc_out="${CMAKE_BINARY_DIR}"
         --cpp_out="${CMAKE_BINARY_DIR}"
         -I "${PROTO_PATH}"
         --plugin=protoc-gen-grpc="${GRPC_CPP_PLUGIN}"
         "${PROTO_FILE}"
    DEPENDS "${PROTO_FILE}"
)

# Include generated files
include_directories(${CMAKE_BINARY_DIR})

# Server executable
add_executable(server
    server.cpp
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

target_link_libraries(server
    gRPC::grpc++
    protobuf::libprotobuf
    Threads::Threads
)

# Optional: Enable AddressSanitizer for debug builds
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_options(server PRIVATE -fsanitize=address -fno-omit-frame-pointer)
    target_link_options(server PRIVATE -fsanitize=address)
endif()
