# System Architecture

The key priority of this architecture is developer velocity.

* Vercel + Railway + Supabase + Beam has been a fantastic combo.

<figure><img src="../.gitbook/assets/CleanShot 2024-05-01 at 09.59.59.png" alt=""><figcaption><p>System architecture as of May 1st, 2024.</p></figcaption></figure>

### User-defined Custom Tool Use by LLM

Using N8N for a user-friendly GUI to define custom tools. This way, any user can give their chatbot custom tools that will be automatically invoked when appropriate, as decided by the LLM.

More coming soon (May-June 2024).

## Self-hostable version (coming July 2024)

Simplify to a single Docker-compose script.

* PostgreSQL[^1]: Main or "top level" storage, contains pointers to all other DBs and additional metadata.&#x20;
* MinIO: File storage (pdf/docx/mp4)&#x20;
* Redis/[ValKey](https://github.com/valkey-io/valkey): User and project metadata, fast retrieval needed for page load.&#x20;
* Qdrant: Vector DB for document embeddings.

<figure><img src="../.gitbook/assets/CleanShot 2024-05-01 at 09.57.08.png" alt=""><figcaption></figcaption></figure>

[^1]: 
