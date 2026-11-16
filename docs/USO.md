# Uso de SICSI

## Servicios y gestiones

Inicia sesión con el usuario creado mediante createsuperuser. La sección Servicios permite altas, edición, filtros y detalle. Los campos código y nombre son obligatorios. No completes información desconocida. La moneda es opcional y usa tres letras mayúsculas (GTQ, USD, etc.).

Si las fechas se contradicen, marca Requiere validación y explica el motivo. Hasta confirmar la información, ese registro queda fuera del cálculo de alertas. Permanente queda excluido aun si conserva una fecha de referencia. Cancelado también se excluye; Suspendido conserva el vencimiento contractual.

Cada servicio tiene un trámite vigente. Registrar gestión agrega un hecho a la bitácora con fecha, tipo, descripción, estado, expediente, siguiente seguimiento y observaciones. Cambiar el estado desde Editar servicio también deja una entrada. No se editan ni borran movimientos históricos.

La lista Gestiones muestra el último movimiento de cada trámite abierto. El indicador de pendientes cuenta servicios cuyo trámite no está Renovado o Cancelado, aunque todavía no tengan gestiones. Aprobado sigue pendiente hasta confirmar la renovación. Si un servicio no tiene movimientos, ábrelo desde Servicios para registrar el primero.

## Renovaciones

Usa Confirmar renovación para guardar la nueva vigencia. La fecha debe ser posterior al vencimiento actual y no anterior al nuevo inicio. Se conservan las fechas anteriores, se crea el historial, se incrementa el ciclo y se registra una gestión. Renovado indica que se completó la renovación anterior; el nuevo ciclo seguirá generando avisos cuando corresponda.

Si un ciclo ya tiene avisos, su vencimiento no puede sustituirse con una edición simple: debe registrarse la renovación. El formulario también detecta si alguien o una operación modificó el servicio mientras estaba abierto; recarga para evitar sobrescribir cambios recientes.

Eliminar solo se permite sin historial, documentos, renovaciones ni alertas. Para conservar un servicio con historial, utiliza Estado del servicio = Cancelado y, cuando corresponda, Trámite = Cancelado.

## Documentos

Adjunta PDF desde el detalle y, opcionalmente, asócialo a una gestión del mismo servicio. Se comprueban extensión, MIME, cabecera, terminador y tamaño. Se almacenan con nombres aleatorios y se descargan únicamente con sesión.

La comprobación de estructura no es un antivirus; usa documentos institucionales confiables y las herramientas de revisión de la institución. Para conservar un acta íntegra con credenciales e identificación utiliza el módulo privado de actas y su comando de importación, documentado en ACTAS.md. No expongas PRIVATE_MEDIA_ROOT como una carpeta web pública.

## Dashboard y avisos

Todos los días se interpretan en America/Guatemala. Los grupos son: anteriores a hoy (vencidos), de hoy a 15 días, 16–30 y 31–45. Sin fecha confirmada incluye fecha vacía o pendiente de validar, excluyendo permanentes. Renovaciones completadas cuenta todos los ciclos históricos registrados.

Los avisos normales se generan solo a 45, 30 y 15 días exactos. Si un servicio se registra cuando ya pasó algún umbral, muestra advertencia y permite un aviso inicial de urgencia (una vez por ciclo). No se inventan notificaciones retroactivas. El día 45 corresponde al aviso normal; la urgencia comienza al quedar menos de 45 días, incluidos los vencidos.

Estado de los avisos:

- Reservada: el sistema registró la clave única antes de intentar SMTP.
- Enviando: comenzó el intento; un cierre inesperado puede dejarlo aquí.
- Enviada: SMTP aceptó DATA y se guardó su respuesta; no garantiza llegada final a la bandeja.
- Fallida o incierta: error de conexión, rechazo o resultado ambiguo.
- Simulada: modo de desarrollo; se imprimió o generó el mensaje sin SMTP real.

Ninguna reserva se reintenta automáticamente, incluso tras fallos, para evitar duplicados en resultados ambiguos. Revisa el proveedor SMTP antes de cualquier recuperación. No borres alertas para forzar reenvíos. Al cambiar de consola a SMTP, los avisos simulados siguen ocupando su clave: prueba SMTP con un servicio de prueba nuevo y elimina ese servicio solo antes de generar historial, o conserva su cancelación como evidencia de la prueba.

## Reportes y seguridad

Los filtros aceptan servicio/código parcial; proveedor y categoría completos sin distinguir mayúsculas; estados; trámite y rango de vencimiento inclusivo. Renovaciones próximas abarca hoy a 45 días y respeta exclusiones. Gestiones pendientes incluye servicios con trámites sin cerrar, aun sin fecha. Exportaciones incluyen última gestión, expediente y seguimiento; Excel trata los textos como datos, no fórmulas.

Seguridad permite cambiar contraseña y cierra las demás sesiones. Salir cierra la sesión actual. Hay límite persistente de 5 fallos por dirección observada por el servidor y 15 globales por 15 minutos. Las direcciones se transforman con HMAC; no se confía en X-Forwarded-For arbitrario. Detrás de un proxy puede aplicarse el límite por IP del proxy; confirma la configuración de red antes de ajustar este comportamiento.

Auditoría conserva cambios de negocio, renovaciones, importaciones, exportaciones y accesos. No registra contraseñas ni hashes de autenticación. No reemplaza un registro externo inalterable: un operador con acceso directo a la base podría cambiar las tablas.

## Actas completas

Actas de entrega conserva el DOCX original cifrado, la transcripción completa, los accesos y el catálogo con todas sus filas. La lectura y descarga exigen sesión y quedan auditadas. El contenido privado se muestra íntegro en la vista del acta, no se incorpora a exportaciones generales de servicios ni se publica en Git. Respalda también private_media/.acta.key: la base cifrada por sí sola no permite recuperar esos datos. Consulta ACTAS.md para importar desde tu PC.
