# Value Eval — general × postgresql index types btree gin gist performance

**Mode:** general  
**Query:** postgresql index types btree gin gist performance  
**Pool size (filtered):** 40  
**google_count:** 0  
**full_pool:** 230  | **capped_pool:** 40  
**filtered_capped:** 40  

## Pool (oracle input — url/title/snippet only)

1. https://appmaster.io/blog/btree-gin-gist-index-decision-table
   Title: B-tree vs GIN vs GiST indexes: a practical PostgreSQL guide
   Snippet: B-tree vs GIN vs GiST indexes: use a decision table to pick the right PostgreSQL index for filters, search, JSONB fields, geo queries, and high-cardinality columns.

2. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
   Title: How to Choose Between Index Types (B-tree, GIN, GiST) in PostgreSQL
   Snippet: Choosing the right index type in PostgreSQL can make the difference between blazing-fast queries and sluggish performance. While B-tree indexes are the default and work for most situations, GIN and Gi

3. https://dba.stackexchange.com/questions/46685/index-method-for-very-few-updates-and-many-inserts
   Title: postgresql - Index method for very few updates and many inserts
   Snippet: As a rule of thumb, a GIN index is faster to search than a GiST index, but slower to build or update; so GIN is better suited for static data and ...

4. https://docs.bswen.com/blog/2026-04-20-postgresql-index-types-guide/
   Title: PostgreSQL Index Types: B-tree vs BRIN vs GIN - When to Use Each
   Snippet: Learn how to choose the right PostgreSQL index type for your query patterns. Compare B-tree, BRIN, GIN, and GiST with real production examples.

5. https://doi.org/10.1007/978-1-4842-5663-3
   Title: PostgreSQL Configuration
   Snippet: Shaik, B. (2020)

6. https://doi.org/10.1007/978-1-4842-5663-3_1
   Title: Best Ways to Install PostgreSQL
   Snippet: Shaik, B. (2020), PostgreSQL Configuration

7. https://doi.org/10.1007/978-1-4842-5663-3_5
   Title: Enable Logging of Your Database and Monitoring PostgreSQL Instances
   Snippet: Shaik, B. (2020), PostgreSQL Configuration

8. https://doi.org/10.1007/s10707-020-00407-w
   Title: MongoDB Vs PostgreSQL: A comparative study on performance aspects
   Snippet: Abstract Several modern day problems need to deal with large amounts of spatio-temporal data. As such, in order to meet the application requirements, more and more systems are adapting to the specific

9. https://doi.org/10.1007/springerreference_62191
   Title: GiST Index
   Snippet: 

10. https://doi.org/10.1088/1742-6596/944/1/012022
   Title: Improving generalized inverted index lock wait times
   Snippet: Concurrent operations on tree like data structures is a cornerstone of any database system. Concurrent operations intended for improving read\write performance and usually implemented via some way of 

11. https://doi.org/10.1097/01.ana.0000187778.94201.f7
   Title: Performance of the Bispectral Index During Electrocautery
   Snippet: T, G. et al. (2005), Journal of Neurosurgical Anesthesiology

12. https://doi.org/10.1109/informatics47936.2019.9119265
   Title: An implementation of the M-tree index structure for PostgreSQL using GiST
   Snippet: Donko, I. et al. (2019), 2019 IEEE 15th International Scientific Conference on Informatics

13. https://doi.org/10.1515/9781503604100-012
   Title: INDEX
   Snippet: (2020), The Gist of Reading

14. https://doi.org/10.20944/preprints202511.2170.v1
   Title: Indexing in PostgreSQL: Performance Evaluation and Use Cases
   Snippet: Efficient indexing remains a central factor in achieving predictable performance in modern relational database systems. PostgreSQL provides six native index types—B-Tree, Hash, GiST, SP-GiST, GIN, and

15. https://doi.org/10.3139/9783446473157.bm
   Title: Index
   Snippet: Fröhlich, L. (2022), PostgreSQL

16. https://doi.org/10.48550/arxiv.2307.06621
   Title: cjdb: a simple, fast, and lean database solution for the CityGML data model
   Snippet: When it comes to storing 3D city models in a database, the implementation of the CityGML data model can be quite demanding and often results in complicated schemas. As an example, 3DCityDB, a widely u

17. https://doi.org/10.64149/j.ijesrt.15.4.22-31
   Title: A COMPARATIVE EXPERIMENTAL STUDY OF INDEX PERFORMANCE IN MONGODB AND POSTGRESQL
   Snippet: The continuous growth in data volumes, combined with the increasing complexity of modern enterprise information systems, requires database management systems (DBMS) to guarantee ever faster response t

18. https://elephanttamer.net/?p=9
   Title: GiST vs GIN index for LIKE searches – a comparison
   Snippet: Takeaway: always use GIN for trigram indexing, and if your database suffers from poor LIKE performance, check not only the scan type, but also the ...

19. https://habr.com/ru/company/postgrespro/blog/441962/
   Title: Indexes in PostgreSQL
   Snippet: habr.com

20. https://hakibenita.com/postgresql-correlation-brin-multi-minmax
   Title: When Good Correlation is Not Enough
   Snippet: hakibenita.com

21. https://hakibenita.com/postgresql-hash-index
   Title: Re-Introducing Hash Indexes in PostgreSQL
   Snippet: hakibenita.com

22. https://medium.com/@andreyalth/understanding-index-methods-b-tree-hash-gin-gist-sp-gist-brin-postgressql-4f3ddfc263a3
   Title: Understanding index methods — B-Tree — Hash — GIN — GiST - Medium
   Snippet: The sp-gist index is used to complex data like 2 dimentional data o multidimentional data, the main difference between sp-gist and gist is tha sp-gist split the data in no-overlapping space.

23. https://ntsd.dev/postgresql-index-types/
   Title: Explain index types in PostgreSQL | Jirawat Boonkumnerd
   Snippet: Postgres provides many index types such as B-tree, hash, GiST, and GIN. ... GiST and GIN are indexes for supporting Full-Text Search which I’ll ...

24. https://oneuptime.com/blog/post/2026-01-25-use-index-types-effectively-postgresql/view
   Title: How to Use Index Types Effectively in PostgreSQL
   Snippet: Learn how to choose and use the right index types in PostgreSQL. This guide covers B-tree, Hash, GIN, GiST, BRIN, and partial indexes with practical examples for optimal query performance.

25. https://openalex.org/W2612672839
   Title: PostgreSQL database performance optimization
   Snippet: The thesis was request by Marlevo software Oy for a general description of the PostgreSQL database and its performance optimization technics. Its purpose was to help new PostgreSQL users to quickly un

26. https://openalex.org/W2896189947
   Title: Highly Efficient Search In Linguistic Data
   Snippet: Electronic dictionaries and online learning services have become a common tool for translators, linguistics and people trying to learn a new language.This master's thesis work has been carried out in 

27. https://stackoverflow.com/questions/12738997/postgres-gist-vs-btree-index
   Title: postgresql - Postgres GIST vs Btree index - Stack Overflow
   Snippet: It's considerably slower than regular b-tree indexes, but allows you to create a multi-column index that contains both GiST-only types and regular ...

28. https://stackoverflow.com/questions/1540374/why-are-postgresql-text-search-gist-indexes-so-much-slower-than-gin-indexes
   Title: performance - Why are PostgreSQL Text-Search GiST indexes so
   Snippet: The docs have a nice overview of the performance differences between GiST and GIN indexes if you're interested: GiST and GIN Index Types .

29. https://stackoverflow.com/questions/21830/postgresql-gin-or-gist-indexes
   Title: indexing - PostgreSQL: GIN or GiST indexes? - Stack Overflow
   Snippet: First of all, do you need to use them for text search indexing? GIN and GiST are index specialized for some data types.

30. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
   Title: postgresql - BTREE vs GIN vs GIST index - Stack Overflow
   Snippet: 5 From PostgreSQL documentation: 11.2. Index Types By default, the CREATE INDEX command creates B-tree indexes The other index types are selected by writing the keyword USING followed by the index typ

31. https://stackoverflow.com/questions/766488/whats-the-difference-between-b-tree-and-gist-index-methods-in-postgresql
   Title: indexing - What's the difference between B-Tree and GiST
   Snippet: There was a recent post on the PG lists about a huge performance hit for using GiST indexes; they're expected to be slower than B-Trees (such is the ...

32. https://www.2ndquadrant.com/en/blog/parallelism-comes-to-vacuum/
   Title: Parallelism comes to VACUUM
   Snippet: 2ndquadrant.com

33. https://www.depesz.com/2014/05/12/joining-btree-and-gingist-indexes/
   Title: Joining BTree and GIN/GiST indexes – select * from depesz;
   Snippet: ... gin_btree (there is also gist_btree if your “ base" index ... What it is – it adds “ btree" type of operators support to gin index.

34. https://www.elysiate.com/blog/best-postgresql-indexes-for-performance
   Title: Best PostgreSQL Indexes for Performance | Elysiate
   Snippet: A practical PostgreSQL guide to choosing the best indexes for performance, including B-tree, GIN, GiST, BRIN, partial, multicolumn, covering, and expression indexes.

35. https://www.meerako.com/blogs/postgresql-indexing-strategies-btree-gin-gist-guide
   Title: PostgreSQL Indexing Deep Dive | Meerako
   Snippet: PostgreSQL Indexing Deep Dive: B-Tree, GIN, GiST, and When to Use Them Slow queries? The right index is magic. Our Postgres experts explain different index types (B-Tree, GIN, GiST) and how to optimiz

36. https://www.mydbops.com/blog/postgresql-indexing-best-practices-guide
   Title: PostgreSQL Index Best Practices for Faster Queries | Mydbops
   Snippet: Boost PostgreSQL query performance with the right indexing strategies. Learn best practices for using B-Tree, Hash, GIN, and more to Contact Mydbops today.

37. https://www.percona.com/blog/2019/06/21/hypothetical-indexes-in-postgresql/
   Title: Hypothetical Indexes in PostgreSQL
   Snippet: percona.com

38. https://www.postgresql.org/about/news/postgresql-18-beta-1-released-3070/
   Title: PostgreSQL 18 Beta 1 Released
   Snippet: postgresql.org

39. https://www.postgresql.org/docs/current/indexes-types.html
   Title: PostgreSQL: Documentation: 18: 11.2. Index Types
   Snippet: PostgreSQL provides several index types: B-tree, Hash, GiST, SP-GiST, GIN, BRIN, and the extension bloom. Each index type uses a different algorithm that is best suited to different types of indexable

40. https://www.thenile.dev/docs/extensions/btree_gin
   Title: Btree_gin - Nile Documentation
   Snippet: The btree_gin extension in PostgreSQL enables GIN indexes to support B-tree indexable data types. ... GIN index with btree_gin is useful when ...

## Oracle Selection

1. https://www.postgresql.org/docs/current/indexes-types.html
   Rationale: Official PostgreSQL documentation on index types — canonical primary reference covering B-tree, Hash, GiST, SP-GiST, GIN, and BRIN with algorithm descriptions.

2. https://doi.org/10.20944/preprints202511.2170.v1
   Rationale: Empirical comparative study of all six native PostgreSQL index types across OLTP, OLAP, full-text, JSONB, spatial, and time-series workloads — synthesizes benchmark evidence into a recommendation matrix.

3. https://appmaster.io/blog/btree-gin-gist-index-decision-table
   Rationale: Practical decision table comparing B-tree, GIN, and GiST indexes — directly addresses the query with actionable guidance for filters, JSONB, geo queries, and high-cardinality columns.

4. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
   Rationale: How to choose between B-tree, GIN, and GiST — directly named to the query, explains performance trade-offs and use-case matching.

5. https://www.elysiate.com/blog/best-postgresql-indexes-for-performance
   Rationale: Comprehensive performance guide covering B-tree, GIN, GiST, BRIN, partial, multicolumn, covering, and expression indexes — performance-oriented, directly answers the query.

6. https://hakibenita.com/postgresql-hash-index
   Rationale: Haki Benita (PostgreSQL expert practitioner) on hash indexes vs. B-tree — authoritative real-world performance comparison from a well-known PG specialist blog.

7. https://elephanttamer.net/?p=9
   Rationale: GiST vs GIN comparison for LIKE/trigram searches — specific empirical benchmark, actionable takeaway (always GIN for trigram indexing).

8. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
   Rationale: Stack Overflow canonical answer comparing B-tree, GIN, and GiST — cites official documentation and summarizes the operator-class differences clearly.

9. https://habr.com/ru/company/postgrespro/blog/441962/
   Rationale: PostgresPro (core PostgreSQL team) deep-dive on indexes — authoritative source from the development community.

10. https://www.meerako.com/blogs/postgresql-indexing-strategies-btree-gin-gist-guide
   Rationale: PostgreSQL indexing deep dive specifically on B-Tree, GIN, and GiST strategies — title and content directly match the query terms.

## C-Method Top-10s

### C1 Overlap-Count — 0ms

1. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
2. https://doi.org/10.1109/informatics47936.2019.9119265
3. https://www.postgresql.org/docs/current/indexes-types.html
4. https://habr.com/ru/company/postgrespro/blog/441962/
5. https://doi.org/10.1007/s10707-020-00407-w
6. https://doi.org/10.1007/978-1-4842-5663-3_1
7. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
8. https://stackoverflow.com/questions/21830/postgresql-gin-or-gist-indexes
9. https://hakibenita.com/postgresql-correlation-brin-multi-minmax
10. https://doi.org/10.1088/1742-6596/944/1/012022

### C2 BM25 vanilla — 2ms

1. https://stackoverflow.com/questions/1540374/why-are-postgresql-text-search-gist-indexes-so-much-slower-than-gin-indexes
2. https://oneuptime.com/blog/post/2026-01-25-use-index-types-effectively-postgresql/view
3. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
4. https://ntsd.dev/postgresql-index-types/
5. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
6. https://stackoverflow.com/questions/21830/postgresql-gin-or-gist-indexes
7. https://www.meerako.com/blogs/postgresql-indexing-strategies-btree-gin-gist-guide
8. https://docs.bswen.com/blog/2026-04-20-postgresql-index-types-guide/
9. https://www.postgresql.org/docs/current/indexes-types.html
10. https://stackoverflow.com/questions/12738997/postgres-gist-vs-btree-index

### C2' BM25-Capped — 1ms

1. https://stackoverflow.com/questions/1540374/why-are-postgresql-text-search-gist-indexes-so-much-slower-than-gin-indexes
2. https://oneuptime.com/blog/post/2026-01-25-use-index-types-effectively-postgresql/view
3. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
4. https://ntsd.dev/postgresql-index-types/
5. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
6. https://www.meerako.com/blogs/postgresql-indexing-strategies-btree-gin-gist-guide
7. https://stackoverflow.com/questions/21830/postgresql-gin-or-gist-indexes
8. https://docs.bswen.com/blog/2026-04-20-postgresql-index-types-guide/
9. https://www.postgresql.org/docs/current/indexes-types.html
10. https://stackoverflow.com/questions/12738997/postgres-gist-vs-btree-index

### C3 Cross-Encoder — 1405ms

1. https://blog.devops.dev/how-to-choose-between-index-types-b-tree-gin-gist-in-postgresql-2954638ec4b6
2. https://docs.bswen.com/blog/2026-04-20-postgresql-index-types-guide/
3. https://www.meerako.com/blogs/postgresql-indexing-strategies-btree-gin-gist-guide
4. https://oneuptime.com/blog/post/2026-01-25-use-index-types-effectively-postgresql/view
5. https://ntsd.dev/postgresql-index-types/
6. https://appmaster.io/blog/btree-gin-gist-index-decision-table
7. https://doi.org/10.20944/preprints202511.2170.v1
8. https://www.postgresql.org/docs/current/indexes-types.html
9. https://stackoverflow.com/questions/40780825/btree-vs-gin-vs-gist-index
10. https://stackoverflow.com/questions/1540374/why-are-postgresql-text-search-gist-indexes-so-much-slower-than-gin-indexes

## Comparison (Oracle vs Methods)

| Method | Jaccard | Oracle URLs captured |
|--------|---------|----------------------|
| C1 Overlap-Count | 0.250 | 4 / 10 |
| C2 BM25 vanilla | 0.250 | 4 / 10 |
| C2' BM25-Capped | 0.250 | 4 / 10 |
| C3 Cross-Encoder | 0.429 | 6 / 10 |

### Oracle URLs missed by all methods

- https://www.elysiate.com/blog/best-postgresql-indexes-for-performance
- https://hakibenita.com/postgresql-hash-index
- https://elephanttamer.net/?p=9
