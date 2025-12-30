cmake_minimum_required(VERSION 3.16)
project(raft_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# Find the gRPC C++ plugin
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin)

# Proto file
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../proto/raft.proto")

# Generate protobuf and gRPC sources
set(PROTO_SRCS "${CMAKE_CURRENT_BINARY_DIR}/raft.pb.cc")
set(PROTO_HDRS "${CMAKE_CURRENT_BINARY_DIR}/raft.pb.h")
set(GRPC_SRCS "${CMAKE_CURRENT_BINARY_DIR}/raft.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_CURRENT_BINARY_DIR}/raft.grpc.pb.h")

add_custom_command(
    OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND protobuf::protoc
    ARGS --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
         --cpp_out "${CMAKE_CURRENT_BINARY_DIR}"
         -I "${CMAKE_CURRENT_SOURCE_DIR}/../proto"
         --plugin=protoc-gen-grpc="${GRPC_CPP_PLUGIN}"
         "${PROTO_FILE}"
    DEPENDS "${PROTO_FILE}"
)

# Include generated headers
include_directories("${CMAKE_CURRENT_BINARY_DIR}")

# Build the server executable
add_executable(server
    server.cpp
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

target_link_libraries(server
    gRPC::grpc++
    gRPC::grpc++_reflection
    protobuf::libprotobuf
    Threads::Threads
)

# Install
install(TARGETS server DESTINATION bin)
