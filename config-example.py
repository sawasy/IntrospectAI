project_name = "IntrospectAI"
project_data_dir = f"/path/to/repo/{project_name}"
temp_dir = "/tmp"
data_dir = f"{project_data_dir}/data"

your_name = "Example User"
your_short_names = ["Ex", "Example"]
default_email = "example@example.com"

# Databases
qdrant_api_key = "SOME KEY HERE"
qdrant_host = "localhost"
qdrant_port = "6333"
qdrant_url = f"http://{qdrant_host}:{qdrant_port}"

# Neo4j
neo4j_url = "bolt://localhost:7687"
neo4j_login = ""
neo4j_pw = ""

sqlite_dir = f"{data_dir}/sqlite"
sqlite_email_file = f"{sqlite_dir}/introspect_ai_email.db"

# LLM
llm_model = "phi4:latest"
llm_cypher_model = "qwen2.5:14b"
llm_asking_model = "phi4:latest"
llm_recheck_model = "granite3.1-dense:8b"
llm_facts_model = "phi4:latest"
llm_embeddings_model = "nomic-embed-text"
llm_relationship_model = "granite3.1-dense:8b"
llm_url = "http://localhost:11434"

# Directories
summaries_dir = f"{data_dir}/summaries"
graphs_dir = f"{data_dir}/graph"
facts_dir = f"{data_dir}/facts"
embeddings_dir = f"{data_dir}/embeddings"

blog_facts_dir = f"{facts_dir}/blog"
email_facts_dir = f"{facts_dir}/email"
journal_facts_dir = f"{facts_dir}/journal"
location_facts_dir = f"{facts_dir}/locations"
tweet_facts_dir = f"{facts_dir}/tweets"

tweet_embeddings_dir = f"{embeddings_dir}/tweets"
blog_embeddings_dir = f"{embeddings_dir}/blog"
email_embeddings_dir = f"{embeddings_dir}/email"
journal_embeddings_dir = f"{embeddings_dir}/journal"
trakttv_embeddings_dir = f"{embeddings_dir}/trakttv"

email_graphs_dir = f"{graphs_dir}/email"
journal_graphs_dir = f"{graphs_dir}/journal"
blog_graphs_dir = f"{graphs_dir}/blog"


# Openstreet lookup
nominatim_url = ""

emails_dict = {
    "example@example.com": "Example User",
    "another-example@example.com": "Example User",
    # Add more entries as needed...
}
