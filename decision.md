The problem statement:

## Turn messy documents into structured, queryable data

Build a system that takes unstructured or semi-structured documents and converts them into clean, structured data that can be searched and queried.

### Reason for selecting this

Selecting the problem statement to convert unstructured data to structured queriable data because I think this is at an intersection of research + developement and I can directly hop onto solving the problem while the user facing parts/data capture/generic integration are minimal.

### Let's elaborate on the problem that I will try to solve
Everything other than what is present in tables or spread sheet or
any schematic structure is unstructured data. Thus videos, documents,
pdfs, even a set of images is unstructured data from which we can fetch
relevant details and convert them into some structured form.

The primary focus of the problem is to deal with messy documents. The
documents can be of different formats, can have varied name philosophy,
can have tables, images and other content embedded. Thus defining a 
single schema is kind of difficult.

The above problem never states which domain the documents are related
with, thus either we treat this as a problem dealing with arbitary type
of documents or we pick up a domain like accounting bills, or prescriptions.

In most of the cases, we will always have to deal with some domain specific documents but of different types.

The domain I am taking is medical where they type of documents would
be prescriptions, diagnostic reports, lab reports, medicine bills etc.

This 