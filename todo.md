# TODO

Known gaps that are not scheduled yet. Move an item to a Linear ticket when it becomes worth doing.

## Rare scenarios

### Two foreign keys between the same tables that share their first column pair

Tracked in Linear: [ANT-47](https://linear.app/antbot/issue/ANT-47).

`EntityNode.find_edge` and `Graph.remove_foreign_key` match an edge on its **first column
pair only**. Suppose two foreign keys go between the same two tables and both start with the
same column pair. Then they cannot be told apart, and a lookup or removal may hit the wrong one.

When it happens: mainly multi-tenant schemas where every key starts with `tenant_id`:

```sql
shipments(tenant_id, order_id)        -> orders(tenant_id, id)
shipments(tenant_id, return_order_id) -> orders(tenant_id, id)
```

Not affected: several foreign keys between the same tables on different columns, such as
`flights.origin_id` and `flights.destination_id` both pointing at `airports.id`. Their first
pairs differ.

Impact today: none in practice. Only the graph's own code and tests call `find_edge` and
`remove_foreign_key`. Join search (`neighbours`, `join_options`, path search) walks all edges
and handles composite keys correctly.

Fix when needed: match on `Edge.column_pairs` (every pair, in order), and add
`Graph.remove_composite_foreign_key(...)`.
