#!/usr/bin/env python3

from langchain_community.graphs import Neo4jGraph

import config

graph = Neo4jGraph(
    url=config.neo4j_url,
    username=config.neo4j_login,
    password=config.neo4j_pw,
)
graph.query("""
            MATCH (n)
            DETACH DELETE n
            """)
