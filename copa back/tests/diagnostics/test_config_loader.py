from rules.config_loader import (
    load_rule_configuration,
    resolve_business_rule,
    get_global_business_rules,
)

# Cargar configuración
config = load_rule_configuration()

print("Configuración cargada:")
print(type(config).__name__)

# Obtener reglas globales
global_rules = get_global_business_rules(config)

print("\nCantidad de reglas globales:")
print(len(global_rules))

# Buscar una regla
rule = resolve_business_rule(
    config,
    "FECHA_FINAL",
    "CONSULTORIA"
)

print("\nRegla FECHA_FINAL:")
print(rule)

# Buscar otra regla
rule = resolve_business_rule(
    config,
    "CODIGO_SERVICIO",
    "SERV_EXT_ENTIDAD_NACIONAL"
)

print("\nRegla CODIGO_SERVICIO:")
print(rule)