# RFC 1035: Domain Names - Implementation and Specification (Fragmentos Operativos)

## 4.1.1. Header section format
El encabezado contiene campos de control, incluidos los códigos de respuesta (RCODE):
- 0 (NOERROR): No error condition.
- 1 (FORMERR): Format error - The name server was unable to interpret the query.
- 2 (SERVFAIL): Server failure - The name server was unable to process this query due to a problem with the name server (e.g. timeout with upstream authoritative server, lame delegation).
- 3 (NXDOMAIN / Name Error): Meaningful only for responses from an authoritative name server, this code signifies that the domain name referenced in the query does not exist.
- 4 (NOTIMP): Not Implemented - The name server does not support the requested kind of query.
- 5 (REFUSED): Refused - The name server refuses to perform the specified operation for policy reasons (e.g. unauthorized zone transfer, recursion disabled for client).

## 4.3. Resolver and Authority Interactions
Cuando un servidor autoritativo recibe una consulta para una zona que administra:
- Si el FQDN coincide pero no existe el tipo de registro (ej. se pide AAAA pero solo existe A), la respuesta debe ser NOERROR con Answer Section vacía (NODATA).
- Si el FQDN no existe bajo la zona administrada, debe devolver RCODE 3 (NXDOMAIN) y el registro SOA de la zona en el Authority Section para permitir el caching negativo según TTL.
