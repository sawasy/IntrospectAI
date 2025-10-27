#!/usr/bin/env python3

from langchain_community.graphs import Neo4jGraph

import config

graph = Neo4jGraph(
    url=config.neo4j_url,
    username=config.neo4j_login,
    password=config.neo4j_pw,
)

# REmove dupliate relationships
dedupliate_relationships = graph.query(
    """
    MATCH (a)-[r1]->(b)<-[r2]-(a)
    WHERE TYPE(r1) = TYPE(r2) AND PROPERTIES(r1) = PROPERTIES(r2)
    WITH a, b, apoc.coll.union(COLLECT(r1), COLLECT(r2))[1..] AS rs
    UNWIND rs as r
    DELETE r
    """
)
