# Retrieval Methods

In RAG (retrieval augmented generation), it's critical to actually retrieve the necessary context to answer a user query. Here's my favorite AI-forward ideas to find the "needle in the haystack" of relevant documents for a user query.

In order of increasing complexity and novelty:

## 1. Standard Vector Retrieval

By default (as of May, 2024) [UIUC.chat](https://www.uiuc.chat/) uses standard vector retrieval lookup. It compares an embedding of the `user query` with embeddings of all the documents in the user's project. The top 80 document chunks are used in final LLM call to answer the user query.

<figure><img src="../.gitbook/assets/how-rag-works (1).png" alt=""><figcaption><p>Generic/simple/standard RAG system.</p></figcaption></figure>

## 2. Parent document retrieval

"Parent document retrieval" refers to _expanding_ the context around the retrieved document chunks. In our case, for each of the top 5 chunks retrieved, we additionally retrieve the 2 preceding and 2 subsequent chunks to the retrieved chunk. In effect, for the closest matches from standard RAG, we grab a little more "above and below" the most relevant chunks/paragraphs we retrieved.&#x20;

Intuitively, we say this solves the "off by one" problem. For example, users as questions like `what is the solution to the Bernoulli equation?`And say we have a textbook in our document corpus. Naively this query embedding matches with the _problem setup_ in the textbook, _**but not the problem solution**_ that follows in the subsequent paragraphs. Therefore, we expand the context to ensure we capture both the problem description and solution in our relevant contexts. This works particularly well for textbook questions.

## 3. Multiple Queries + Filtering

**Key idea:** use an LLM to diversify your queries, then use an LLM to filter out irrelevant passages before we go to big LLM, e.g. GPT-4 (many times more expensive) for final answer generation.

**The retrieval data flow:**&#x20;

1. User query ->&#x20;
2. LLM generates multiple similar queries w/ more keywords ->&#x20;
3. Vector KNN Retrieval & reranking ->&#x20;
4. Filter out truly bad/irrelevant passages w/ small LLM ->&#x20;
5. Get parent docs (see above) for top 5 passages ->&#x20;
6. A set of documents/passages for 'final answer' generation w/ large LLM.

**Challenge:** LLM filtering requires 1-5 seconds at minimum, even fully parallel. Dramatic slowdown to performance. This will get better quickly as small LLMs get smarter & even faster.

## 4. LLM-Guided Retrieval

**Key idea:** It's retrieval with function calling to explore the documents.&#x20;

Mirroring the human research process, we let the LLM decide if the retrieved context is relevant and, more importantly, where to look next. The LLM decides between a set of options like "next page" or "previous page" and similar to explore the document and find the best passages to answer our target question.&#x20;

{% file src="../.gitbook/assets/Final Proposal - LLM Guided Retrieval.pdf" %}

<figure><img src="../.gitbook/assets/CleanShot 2024-05-01 at 15.40.44.png" alt=""><figcaption></figcaption></figure>

LLM Guided retrieval thrives with structured data.&#x20;

### Scientific PDF parsing

* Grobid (with [AllenAI's PaperMerge](https://github.com/allenai/papermage/blob/main/examples/quick\_start\_demo.ipynb) wrapper for great dev experience)
* Nougut&#x20;
* Oreo

### Data layout in SQLite

Our goal is to parse and store academic PDFs with maximally structured information so that LLM's can adeptly explore the documents by "asking" to view PDF sections on demand.

3 tables to store academic PDFs:

1. Papers
2. Section
3. Contexts

**Papers**

"A paper has sections"

<table><thead><tr><th width="91">ULD</th><th>Num tokens</th><th width="78">Title</th><th>Date published</th><th>Journal</th><th>Authors</th><th>Sections</th></tr></thead><tbody><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>[array of pointers to section object]</td></tr></tbody></table>

**Sections**

"A section has contexts"

<table><thead><tr><th>ULD</th><th width="117">Num tokens</th><th>Section title </th><th>Section number</th><th>Contexts</th></tr></thead><tbody><tr><td></td><td></td><td></td><td></td><td>[array of pointers to context object]</td></tr></tbody></table>

**Contexts**

The base unit of text. Each context must fit within a LLM embedding model's context window (typically 8k tokens or more precisely`2^13 = 8,192` tokens).

<table><thead><tr><th width="91">ULD</th><th>Text</th><th width="127">Section title</th><th width="156">Section number</th><th width="125">Num tokens</th><th width="204">embedding-nomic_1.5</th><th width="142">Page number</th><th>stop reason</th></tr></thead><tbody><tr><td></td><td>&#x3C;Raw text></td><td></td><td></td><td></td><td></td><td></td><td>"Section" or "Token limit" if the section is larger than our embedding model context window.</td></tr></tbody></table>

#### SQL details

SQLite, and most SQL implementations, don't allow for a single field to point to an array of foreign keys, so we use the "Junction table" pattern for our one-to-many relationships.

Junction tables simply allow one `paper` to have **many** `sections` and one `section` to have **many** `contexts`.

* `PaperSections` table

```sql
CREATE TABLE PaperSections (
    paper_id INTEGER,
    section_id INTEGER,
    FOREIGN KEY (paper_id) REFERENCES Papers(paper_id),
    FOREIGN KEY (section_id) REFERENCES Sections(section_id),
    PRIMARY KEY (paper_id, section_id)
);
```

* `SectionContexts` table

```sql
CREATE TABLE SectionContexts (
    paper_id INTEGER,
    section_id INTEGER,
    FOREIGN KEY (paper_id) REFERENCES Papers(paper_id),
    FOREIGN KEY (section_id) REFERENCES Sections(section_id),
    PRIMARY KEY (paper_id, section_id)
);
```

We will publish our SQLite files here for PubMed and other academic datasets when available.