"""Neo4j graph operations for the knowledge graph."""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from auto_kg.core.schema import KGEdge, KGNode


class GraphStore:
    """Async interface to Neo4j for KG operations."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def ensure_constraints(self) -> None:
        """Create uniqueness constraints and indexes."""
        assert self._driver is not None
        async with self._driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT kg_node_id IF NOT EXISTS "
                "FOR (n:KGNode) REQUIRE n.id IS UNIQUE"
            )
            await session.run(
                "CREATE INDEX kg_node_type IF NOT EXISTS "
                "FOR (n:KGNode) ON (n.node_type)"
            )

    async def upsert_node(self, node: KGNode) -> None:
        """Create or update a node in the graph."""
        assert self._driver is not None
        props = node.model_dump(mode="json")
        # Flatten temporal into top-level props for Neo4j
        temporal = props.pop("temporal")
        props.update({f"temporal_{k}": v for k, v in temporal.items()})

        async with self._driver.session() as session:
            await session.run(
                "MERGE (n:KGNode {id: $id}) "
                "SET n += $props, n:$label",
                id=node.id,
                props=props,
                label=node.node_type.value,
            )

    async def upsert_edge(self, edge: KGEdge) -> None:
        """Create or update an edge in the graph."""
        assert self._driver is not None
        props = edge.model_dump(mode="json", exclude={"source_id", "target_id", "edge_type"})
        temporal = props.pop("temporal")
        props.update({f"temporal_{k}": v for k, v in temporal.items()})

        async with self._driver.session() as session:
            await session.run(
                f"MATCH (a:KGNode {{id: $src}}), (b:KGNode {{id: $tgt}}) "
                f"MERGE (a)-[r:{edge.edge_type.value}]->(b) "
                "SET r += $props",
                src=edge.source_id,
                tgt=edge.target_id,
                props=props,
            )

    async def get_node(self, node_id: str) -> dict | None:
        """Retrieve a node by ID."""
        assert self._driver is not None
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:KGNode {id: $id}) RETURN n", id=node_id
            )
            record = await result.single()
            return dict(record["n"]) if record else None

    async def get_children(self, node_id: str) -> list[dict]:
        """Get all direct children of a node."""
        assert self._driver is not None
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:KGNode {id: $id})-[:contains]->(child:KGNode) "
                "RETURN child ORDER BY child.numbering",
                id=node_id,
            )
            return [dict(record["child"]) async for record in result]
