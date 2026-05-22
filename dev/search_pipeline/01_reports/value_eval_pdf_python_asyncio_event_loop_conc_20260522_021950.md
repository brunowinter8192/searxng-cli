# Value Eval — pdf × python asyncio event loop concurrency

**Mode:** pdf  
**Query:** python asyncio event loop concurrency  
**Pool size (filtered):** 5  
**google_count:** 0  
**full_pool:** 384  | **capped_pool:** 59  
**filtered_capped:** 5  

## Pool (oracle input — url/title/snippet only)

1. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf
   Title: PDF Using Asyncio in Python 3 - Archive.org
   Snippet: More practical information for shutdown handling is presented later in the book. asyncio in Python exposes a great deal of the underlying machinery around the event loop— and requires you to be aware 

2. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf
   Title: PDF Event-driven Programming with Python asyncio
   Snippet: Event-driven programming techniques are as relevant and important as ever in a lot of problem domains which motivates ﬁrst class language and standard library support Introduced Python's Native Corout

3. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
   Title: PDF Concurrency with AsyncIO - Springer
   Snippet: The asyncio.run() function was introduced in Python 3.7 (older versions of Python such as Python 3.6 required you to explicitly obtain a reference to the Event Loop and to run the root async function 

4. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
   Title: PDF Python Concurrency with asyncio
   Snippet: This makes asynchronous code easy to read and understand, as it looks like the sequential flow most software engineers are familiar with. asyncio is a library to execute these coroutines in an asynchr

5. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf
   Title: PDF Concurrency in Python Concepts, frameworks and best practices - 1emPyCon DE
   Snippet: Control returns to the main loop after the handler execution. Code looks sequential, but execution is switched to other code if the event loop has to wait for I/O. Both variants may be used in the sam

## Oracle Selection

1. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
   Rationale: Matthew Fowler 'Python Concurrency with asyncio' (O'Reilly) — full book PDF covering coroutines, event loop lifecycle, tasks, single-threaded event loop concurrency model in depth.

2. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf
   Rationale: Caleb Hattingh 'Using Asyncio in Python 3' (O'Reilly 2018) — book PDF specifically covering the event loop, its lifetime management, and asyncio's async programming model.

3. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
   Rationale: Springer book chapter 'Concurrency with AsyncIO' — covers asyncio.run(), event loop references, and concurrent task execution with a textbook-quality explanation.

4. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf
   Rationale: Conference slides PDF 'Event-driven Programming with Python asyncio' — covers native coroutine concepts and standard asyncio support for event-driven concurrency.

5. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf
   Rationale: PyCon DE 2018 'Concurrency in Python: concepts, frameworks, and best practices' PDF — explains event loop-based concurrency, asyncio's role, and I/O switching semantics.

## C-Method Top-10s

### C1 Overlap-Count — 0ms

1. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
2. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
3. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf
4. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf
5. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf

### C2 BM25 vanilla — 0ms

1. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
2. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
3. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf
4. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf
5. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf

### C2' BM25-Capped — 0ms

1. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
2. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
3. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf
4. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf
5. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf

### C3 Cross-Encoder — 184ms

1. https://media.githubusercontent.com/media/Rishabh-creator601/Books/refs/heads/master/python_books/Python_Concurrency_with_asyncio_Matthew_Fowler.pdf
2. https://link.springer.com/content/pdf/10.1007/978-3-030-25943-3_34.pdf
3. https://sschwarzer.com/download/concurrency_pycon_de2018.pdf
4. https://indico.gsi.de/event/17490/contributions/71045/attachments/43482/61031/Event-driven%20Programming%20with%20Python%20asyncio.pdf
5. https://archive.org/download/python-programming-collection-pdf-ebooks-all-you-need/Using%20Asyncio%20in%20Python%203_%20Understanding%20Python%27s%20Asynchronous%20Programming%20Features%20%28CONV%29%20-%20Caleb%20Hattingh%20%28O%27Reilly%20Media%3BFree%20Programming%20Ebooks%3B2018%29.pdf

## Comparison (Oracle vs Methods)

| Method | Jaccard | Oracle URLs captured |
|--------|---------|----------------------|
| C1 Overlap-Count | 1.000 | 5 / 5 |
| C2 BM25 vanilla | 1.000 | 5 / 5 |
| C2' BM25-Capped | 1.000 | 5 / 5 |
| C3 Cross-Encoder | 1.000 | 5 / 5 |

### Oracle URLs missed by all methods

_All oracle URLs captured by at least one method._
