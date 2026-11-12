# Procedimiento Operativo Estándar: Diagnóstico de Fallas DNS en Servidores BIND9 (SOP-DNS-01)

## 1. Alcance
Este procedimiento establece los pasos sistemáticos de verificación y diagnóstico ante anomalías en la resolución de nombres DNS gestionados por servidores BIND9 autoritativos o recursivos.

## 2. Clasificación de Síntomas y Árbol de Decisión

### 2.1. Síntoma: Respuesta NXDOMAIN (RCODE 3 / DNS-NXD-01)
- **Definición:** El servidor autoritativo certifica que el nombre de dominio consultado no existe en la zona administrada.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar consulta dirigida con `dig @127.0.0.1 -p 5353 app.internal.corp A +noall +comments +answer`.
  2. Verificar la presencia de la bandera `status: NXDOMAIN` en el encabezado.
  3. Revisar el Authority Section para confirmar el registro SOA retornado.
  4. Revisar los logs de BIND9 (`named.log` / `query.log`) buscando `query failed (NXDOMAIN) for app.internal.corp`.
- **Causa Raíz Típica:**
  - Registro A/AAAA ausente o eliminado en el archivo maestro de zona BIND9.
  - Error tipográfico o FQDN mal formulado por el cliente.
- **Acción Correctiva:**
  - Agregar el registro correspondiente en la zona del servidor BIND9 y recargar la configuración (`rndc reload`).

### 2.2. Síntoma: Respuesta SERVFAIL (RCODE 2 / DNS-SRV-01)
- **Definición:** El resolutor no pudo obtener una respuesta válida de la jerarquía DNS por fallo de servidores autoritativos o DNSSEC.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `dig @127.0.0.1 -p 5353 partner.external.org A +trace` para aislar el salto donde se detiene la resolución.
  2. Verificar la alcanzabilidad del servidor autoritativo remoto mediante ICMP o sondeo en el puerto 53 (UDP/TCP).
  3. Inspeccionar logs buscando `connection timed out resolving partner.external.org` o `broken trust chain (DNSSEC)`.
- **Causa Raíz Típica:**
  - Servidor autoritativo remoto caído o con puerto 53 bloqueado por firewall.
  - Delegación rota (Lame delegation) o fallo de validación criptográfica DNSSEC.
- **Acción Correctiva:**
  - Restaurar conectividad hacia los servidores autoritativos o sincronizar claves DNSSEC y purgar caché (`rndc flush && rndc reload`).

### 2.3. Síntoma: Respuesta REFUSED (RCODE 5 / DNS_REFUSED / DNS-REF-01)
- **Definición:** El servidor autoritativo BIND9 rechaza procesar la consulta por violación de listas de control de acceso (ACL allow-query o match-clients).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `dig @127.0.0.1 -p 5353 restricted.corp.internal A` y verificar `status: REFUSED`.
  2. Inspeccionar logs buscando `query failed (REFUSED) for restricted.corp.internal/IN/A: query refused by ACL`.
  3. Revisar los bloques `acl`, `allow-query` y `allow-recursion` en `named.conf.options`.
- **Causa Raíz Típica:**
  - Subred o IP del cliente excluida de la directiva `allow-query` o vista interna no coincidente.
- **Acción Correctiva:**
  - Autorizar la subred cliente en `/etc/bind/named.conf.options` y recargar BIND9 (`rndc reload`).

### 2.4. Síntoma: Truncamiento DNS y Bloqueo EDNS / TCP (Bandera TC=1 / DNS_TRUNCATED_EDNS / DNS-TRUNC-01)
- **Definición:** La respuesta DNS supera el tamaño de búfer UDP estándar (512 bytes) sin soporte EDNS0 o con bloqueo de reintentos sobre TCP puerto 53.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp` y verificar presencia de bandera `flags: qr tc rd`.
  2. Probar conectividad TCP en puerto 53 mediante `dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +tcp`.
  3. Revisar logs buscando `large response truncated to 512 bytes, client retrying over TCP`.
- **Causa Raíz Típica:**
  - Conjunto de registros voluminoso sin negociación EDNS0 (RFC 6891) o firewall filtrando paquetes TCP/53.
- **Acción Correctiva:**
  - Habilitar soporte EDNS0 y permitir tráfico TCP de entrada en el puerto 53 en el firewall (`iptables -A INPUT -p tcp --dport 53 -j ACCEPT`).

### 2.5. Síntoma: Error de Delegación (Lame Delegation / DELEGATION_ERROR / DNS-DEL-01)
- **Definición:** Los servidores de nombres (NS) delegados en la zona padre no tienen autoridad configurada sobre la zona hija solicitada.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `dig @127.0.0.1 -p 5353 sub.corp.internal NS` y verificar devoluciones con `status: SERVFAIL`.
  2. Consultar directamente a cada servidor NS delegado para verificar si emiten bandera AA (Authoritative Answer).
  3. Inspeccionar logs buscando `lame server resolving sub.corp.internal`.
- **Causa Raíz Típica:**
  - Registros NS o pegamento (glue records) desactualizados o servidores NS sin zona hija cargada.
- **Acción Correctiva:**
  - Sincronizar y corregir los registros NS y glue records en el servidor autoritativo primario (`rndc reload`).
