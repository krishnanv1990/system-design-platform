//! Build script for compiling Protocol Buffer definitions.
//!
//! This script uses tonic-build to generate Rust code from .proto files.
//! The generated code provides the gRPC service traits and message types.

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Compile the HNSW service proto file
    // The proto file should define:
    // - VectorSearchService with Insert, Search, Delete RPCs
    // - Vector message with id and values
    // - SearchRequest/SearchResponse messages

    // Uncomment and adjust path when proto file is available:
    // tonic_build::compile_protos("proto/hnsw.proto")?;

    // For now, we'll use manual service definitions in the main code
    println!("cargo:rerun-if-changed=proto/hnsw.proto");

    Ok(())
}
