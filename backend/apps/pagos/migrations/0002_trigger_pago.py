"""pago (RNF-E-CON-01): sin DELETE ni TRUNCATE; UPDATE solo de estado y referencia_externa
(por ejemplo, cuando la pasarela confirma un pago EN_VERIFICACION)."""

from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION pago_proteger() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
        RAISE EXCEPTION 'pago: % no permitido', TG_OP;
    END IF;
    IF (NEW.id, NEW.cotizacion_id, NEW.reserva_id, NEW.tipo, NEW.monto, NEW.clave_idempotencia, NEW.fecha)
       IS DISTINCT FROM
       (OLD.id, OLD.cotizacion_id, OLD.reserva_id, OLD.tipo, OLD.monto, OLD.clave_idempotencia, OLD.fecha) THEN
        RAISE EXCEPTION 'pago: solo se pueden cambiar estado y referencia_externa';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pago_sin_cambios
    BEFORE UPDATE OR DELETE ON pago
    FOR EACH ROW EXECUTE FUNCTION pago_proteger();

CREATE TRIGGER pago_sin_vaciar
    BEFORE TRUNCATE ON pago
    FOR EACH STATEMENT EXECUTE FUNCTION pago_proteger();
"""

QUITAR = """
DROP TRIGGER IF EXISTS pago_sin_vaciar ON pago;
DROP TRIGGER IF EXISTS pago_sin_cambios ON pago;
DROP FUNCTION IF EXISTS pago_proteger();
"""


class Migration(migrations.Migration):
    dependencies = [("pagos", "0001_initial")]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
