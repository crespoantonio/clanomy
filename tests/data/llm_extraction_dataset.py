"""
55 Real-World Scenarios Dataset for LLM Financial Extraction & Formatting Evaluation.
Covers 1 to 15 items per message, mixing incomes and expenses, amounts at the start,
middle, and end of text, conversational chatter, greetings, and bilingual English/Spanish phrasing.
"""

from typing import List, Dict, Any

DATASET: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1 ITEM SCENARIOS (1 to 10)
    # -------------------------------------------------------------
    {
        "id": "case_01",
        "description": "1 item: Amount at start, Spanish",
        "text": "1500 café con leche",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [1500.0],
        "expected_types": ["expense"]
    },
    {
        "id": "case_02",
        "description": "1 item: Amount in middle, Spanish",
        "text": "Me tomé un café por 1200 pesos en la esquina de casa",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [1200.0],
        "expected_types": ["expense"]
    },
    {
        "id": "case_03",
        "description": "1 item: Amount at end, Spanish",
        "text": "Almuerzo con compañeros de trabajo 4500",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [4500.0],
        "expected_types": ["expense"]
    },
    {
        "id": "case_04",
        "description": "1 item: Heavy conversational noise + amount in middle",
        "text": "Hola clanomy qué tal! Acabo de pagar 3200 de farmacia por los remedios de la abuela, anotámelo porfa",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [3200.0],
        "expected_types": ["expense"]
    },
    {
        "id": "case_05",
        "description": "1 item: English amount in middle",
        "text": "Just spent 24.50 on groceries at trader joes",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [24.50],
        "expected_types": ["expense"]
    },
    {
        "id": "case_06",
        "description": "1 item: English amount at end with explicit currency",
        "text": "uber ride to the airport 35 usd",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [35.0],
        "expected_types": ["expense"]
    },
    {
        "id": "case_07",
        "description": "1 item: Single Income, amount at start",
        "text": "50000 cobro de honorarios freelance",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [50000.0],
        "expected_types": ["income"]
    },
    {
        "id": "case_08",
        "description": "1 item: Single Income, amount in middle with explicit currency",
        "text": "Me depositaron 1500 dólares de sueldo de la empresa",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [1500.0],
        "expected_types": ["income"]
    },
    {
        "id": "case_09",
        "description": "1 item: Single Income, amount at end",
        "text": "Bono de fin de año 300 usd",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [300.0],
        "expected_types": ["income"]
    },
    {
        "id": "case_10",
        "description": "1 item: Scheduled bill with explicit due date",
        "text": "Factura de luz 8500 pesos con vencimiento el 20/09",
        "expected_count": 1,
        "expected_action": "log_transaction",
        "expected_amounts": [8500.0],
        "expected_types": ["expense"]
    },

    # -------------------------------------------------------------
    # 2 ITEMS SCENARIOS (11 to 20)
    # -------------------------------------------------------------
    {
        "id": "case_11",
        "description": "2 items: Inline conjunction 'y' with amounts first",
        "text": "2509 verdu y 5999 almacén",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [2509.0, 5999.0],
        "expected_types": ["expense", "expense"]
    },
    {
        "id": "case_12",
        "description": "2 items: Conversational Spanish with amounts in middle",
        "text": "Gaste 399 en el súper y 599 en nafta",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [399.0, 599.0],
        "expected_types": ["expense", "expense"]
    },
    {
        "id": "case_13",
        "description": "2 items: Amounts at end of concepts",
        "text": "cena sushi 18000 y cine 6000",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [18000.0, 6000.0],
        "expected_types": ["expense", "expense"]
    },
    {
        "id": "case_14",
        "description": "2 items: Mixed 1 income and 1 expense",
        "text": "Cobré 1200 dólares de un trabajo y gasté 150 en una cena",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [1200.0, 150.0],
        "expected_types": ["income", "expense"]
    },
    {
        "id": "case_15",
        "description": "2 items: Mixed income & expense with casual banter",
        "text": "Che bot buenas tardes, me entraron 500 usd de freelance pero ya pagué 80 de internet",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [500.0, 80.0],
        "expected_types": ["income", "expense"]
    },
    {
        "id": "case_16",
        "description": "2 items: English expenses with 'and'",
        "text": "Spent 12 on breakfast and 40 on fuel",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [12.0, 40.0],
        "expected_types": ["expense", "expense"]
    },
    {
        "id": "case_17",
        "description": "2 items: English mixed income and expense",
        "text": "Got paid 2000 salary and bought a monitor for 300",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [2000.0, 300.0],
        "expected_types": ["income", "expense"]
    },
    {
        "id": "case_18",
        "description": "2 items: Incomes only in Spanish",
        "text": "Me pagaron 80000 de sueldo y 15000 de bono",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [80000.0, 15000.0],
        "expected_types": ["income", "income"]
    },
    {
        "id": "case_19",
        "description": "2 items: Multiline newline separated",
        "text": "1200 almuerzo\n350 café",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [1200.0, 350.0],
        "expected_types": ["expense", "expense"]
    },
    {
        "id": "case_20",
        "description": "2 items: Conversational story with amounts in middle",
        "text": "Hola clanomy te cuento que hoy me fundí: compré un libro por 8500 y clavé un café de 2200",
        "expected_count": 2,
        "expected_action": "log_transaction",
        "expected_amounts": [8500.0, 2200.0],
        "expected_types": ["expense", "expense"]
    },

    # -------------------------------------------------------------
    # 3 ITEMS SCENARIOS (21 to 28)
    # -------------------------------------------------------------
    {
        "id": "case_21",
        "description": "3 items: Comma separated list with amounts first",
        "text": "1200 almuerzo, 350 cafe y 800 taxi",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [1200.0, 350.0, 800.0],
        "expected_types": ["expense", "expense", "expense"]
    },
    {
        "id": "case_22",
        "description": "3 items: Amounts in middle of phrases",
        "text": "Pagué 4500 en la carnicería, gasté 1800 en la panadería y dejé 600 de propina",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [4500.0, 1800.0, 600.0],
        "expected_types": ["expense", "expense", "expense"]
    },
    {
        "id": "case_23",
        "description": "3 items: Mixed 1 income and 2 expenses",
        "text": "Cobré 1500 de cliente, gasté 200 en super y 50 de nafta",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [1500.0, 200.0, 50.0],
        "expected_types": ["income", "expense", "expense"]
    },
    {
        "id": "case_24",
        "description": "3 items: English expenses list with explicit USD",
        "text": "Coffee 5 usd, lunch 18 usd, subway pass 2.90 usd",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [5.0, 18.0, 2.90],
        "expected_types": ["expense", "expense", "expense"]
    },
    {
        "id": "case_25",
        "description": "3 items: English mixed 2 incomes and 1 expense",
        "text": "Received 1200 salary, got 150 dividends, paid 400 rent",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [1200.0, 150.0, 400.0],
        "expected_types": ["income", "income", "expense"]
    },
    {
        "id": "case_26",
        "description": "3 items: Amounts at end of items",
        "text": "pan 500, leche 800 y queso 1400",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [500.0, 800.0, 1400.0],
        "expected_types": ["expense", "expense", "expense"]
    },
    {
        "id": "case_27",
        "description": "3 items: Concert chatter with mixed placement",
        "text": "Buenas noches! Vengo del recital: entrada 25000, estacionamiento 5000 y birra 4000",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [25000.0, 5000.0, 4000.0],
        "expected_types": ["expense", "expense", "expense"]
    },
    {
        "id": "case_28",
        "description": "3 items: 3 separate income entries",
        "text": "Entraron 2500 de sueldo, 300 de intereses y 100 de un regalo",
        "expected_count": 3,
        "expected_action": "log_transaction",
        "expected_amounts": [2500.0, 300.0, 100.0],
        "expected_types": ["income", "income", "income"]
    },

    # -------------------------------------------------------------
    # 4 TO 5 ITEMS SCENARIOS (29 to 38)
    # -------------------------------------------------------------
    {
        "id": "case_29",
        "description": "4 items: Food shopping with amounts first",
        "text": "Gastos de hoy: 2500 verduleria, 4800 carniceria, 1200 panaderia y 600 helado",
        "expected_count": 4,
        "expected_action": "log_transaction",
        "expected_amounts": [2500.0, 4800.0, 1200.0, 600.0],
        "expected_types": ["expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_30",
        "description": "4 items: Mixed 2 incomes and 2 expenses",
        "text": "Cobré 3000 de sueldo y 200 de venta de ropa, pagué 800 de alquiler y 120 de luz",
        "expected_count": 4,
        "expected_action": "log_transaction",
        "expected_amounts": [3000.0, 200.0, 800.0, 120.0],
        "expected_types": ["income", "income", "expense", "expense"]
    },
    {
        "id": "case_31",
        "description": "4 items: Amounts in middle with verbs",
        "text": "Compré por 3500 un libro, gasté 1500 en merienda, pagué 2800 de farmacia y 1100 en uber",
        "expected_count": 4,
        "expected_action": "log_transaction",
        "expected_amounts": [3500.0, 1500.0, 2800.0, 1100.0],
        "expected_types": ["expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_32",
        "description": "4 items: English day breakdown",
        "text": "20 lunch, 5 coffee, 15 taxi, and 60 groceries",
        "expected_count": 4,
        "expected_action": "log_transaction",
        "expected_amounts": [20.0, 5.0, 15.0, 60.0],
        "expected_types": ["expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_33",
        "description": "5 items: Mall trip in Spanish",
        "text": "Shopping con la familia: remera 15000, pantalon 28000, zapatillas 45000, cine 8000 y pochoclos 3500",
        "expected_count": 5,
        "expected_action": "log_transaction",
        "expected_amounts": [15000.0, 28000.0, 45000.0, 8000.0, 3500.0],
        "expected_types": ["expense", "expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_34",
        "description": "5 items: Mixed 2 incomes and 3 expenses with travel chatter",
        "text": "Me pagaron 2500 usd de proyecto, 300 de bono, gasté 450 en vuelos, 120 en hotel y 80 en comidas",
        "expected_count": 5,
        "expected_action": "log_transaction",
        "expected_amounts": [2500.0, 300.0, 450.0, 120.0, 80.0],
        "expected_types": ["income", "income", "expense", "expense", "expense"]
    },
    {
        "id": "case_35",
        "description": "5 items: Amounts in middle with past verbs",
        "text": "Ayer gasté 800 en café, 2400 en almuerzo, 1100 en peaje, 5500 en combustible y 3200 en el súper",
        "expected_count": 5,
        "expected_action": "log_transaction",
        "expected_amounts": [800.0, 2400.0, 1100.0, 5500.0, 3200.0],
        "expected_types": ["expense", "expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_36",
        "description": "5 items: English mixed 2 incomes and 3 expenses",
        "text": "Earned 4000 salary, received 100 cashback, paid 1200 rent, 90 internet, and 150 groceries",
        "expected_count": 5,
        "expected_action": "log_transaction",
        "expected_amounts": [4000.0, 100.0, 1200.0, 90.0, 150.0],
        "expected_types": ["income", "income", "expense", "expense", "expense"]
    },
    {
        "id": "case_37",
        "description": "4 items: Multiline bill payments",
        "text": "Internet 6500\nLuz 4200\nGas 2100\nAgua 1500",
        "expected_count": 4,
        "expected_action": "log_transaction",
        "expected_amounts": [6500.0, 4200.0, 2100.0, 1500.0],
        "expected_types": ["expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_38",
        "description": "5 items: Conversational opening and closing with diverse expenses",
        "text": "Hola Clanomy! Día movido: cargué 15000 de nafta, compré 4200 en verdura, 8900 en el super, 1500 café y 2300 de farmacia",
        "expected_count": 5,
        "expected_action": "log_transaction",
        "expected_amounts": [15000.0, 4200.0, 8900.0, 1500.0, 2300.0],
        "expected_types": ["expense", "expense", "expense", "expense", "expense"]
    },

    # -------------------------------------------------------------
    # 6 TO 10 ITEMS SCENARIOS (39 to 48)
    # -------------------------------------------------------------
    {
        "id": "case_39",
        "description": "6 items: Grocery cart items",
        "text": "Supermercado: leche 950, huevos 1800, fideos 650, arroz 700, carne 7200 y gaseosa 1500",
        "expected_count": 6,
        "expected_action": "log_transaction",
        "expected_amounts": [950.0, 1800.0, 650.0, 700.0, 7200.0, 1500.0],
        "expected_types": ["expense"] * 6
    },
    {
        "id": "case_40",
        "description": "6 items: Mixed 3 incomes and 3 expenses",
        "text": "Balance del día: cobré 1800 de sueldo, 250 de freelance y 50 de reintegro; pagué 500 de tarjeta, 70 de luz y 40 de gas",
        "expected_count": 6,
        "expected_action": "log_transaction",
        "expected_amounts": [1800.0, 250.0, 50.0, 500.0, 70.0, 40.0],
        "expected_types": ["income", "income", "income", "expense", "expense", "expense"]
    },
    {
        "id": "case_41",
        "description": "7 items: Weekly household expenses",
        "text": "Gastos de la semana: verdulería 4500, carnicería 9200, panadería 2100, almacén 6300, farmacia 3800, veterinaria 5500 y remis 2000",
        "expected_count": 7,
        "expected_action": "log_transaction",
        "expected_amounts": [4500.0, 9200.0, 2100.0, 6300.0, 3800.0, 5500.0, 2000.0],
        "expected_types": ["expense"] * 7
    },
    {
        "id": "case_42",
        "description": "7 items: English mixed 2 incomes and 5 expenses",
        "text": "Got paid 3500 wages, 200 refund, spent 50 on fuel, 30 dinner, 15 drinks, 100 utilities, and 85 clothing",
        "expected_count": 7,
        "expected_action": "log_transaction",
        "expected_amounts": [3500.0, 200.0, 50.0, 30.0, 15.0, 100.0, 85.0],
        "expected_types": ["income", "income", "expense", "expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_43",
        "description": "8 items: Hardware store and home improvement items",
        "text": "Ferretería y arreglos: pintura 25000, pinceles 3500, rodillo 4200, lija 1200, tornillos 800, sellador 3100, bombita 1500 y cinta 900",
        "expected_count": 8,
        "expected_action": "log_transaction",
        "expected_amounts": [25000.0, 3500.0, 4200.0, 1200.0, 800.0, 3100.0, 1500.0, 900.0],
        "expected_types": ["expense"] * 8
    },
    {
        "id": "case_44",
        "description": "8 items: Mixed 3 incomes and 5 expenses",
        "text": "Cobré 2200 de sueldo, 400 de clase particular, 150 de venta de bici, y gasté 350 en super, 80 en combustible, 45 en farmacia, 25 en taxi y 60 en cena",
        "expected_count": 8,
        "expected_action": "log_transaction",
        "expected_amounts": [2200.0, 400.0, 150.0, 350.0, 80.0, 45.0, 25.0, 60.0],
        "expected_types": ["income", "income", "income", "expense", "expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_45",
        "description": "9 items: Monthly bill summary",
        "text": "Cuentas del mes: alquiler 120000, expensas 35000, luz 12000, gas 4500, agua 3200, internet 9800, netflix 5500, spotify 2200 y celular 7500",
        "expected_count": 9,
        "expected_action": "log_transaction",
        "expected_amounts": [120000.0, 35000.0, 12000.0, 4500.0, 3200.0, 9800.0, 5500.0, 2200.0, 7500.0],
        "expected_types": ["expense"] * 9
    },
    {
        "id": "case_46",
        "description": "9 items: Mixed 3 incomes and 6 expenses",
        "text": "Ingresos: 4500 sueldo, 500 bono, 200 dividendos. Gastos: 1200 alquiler, 150 luz, 80 internet, 350 super, 60 nafta y 40 farmacia",
        "expected_count": 9,
        "expected_action": "log_transaction",
        "expected_amounts": [4500.0, 500.0, 200.0, 1200.0, 150.0, 80.0, 350.0, 60.0, 40.0],
        "expected_types": ["income", "income", "income", "expense", "expense", "expense", "expense", "expense", "expense"]
    },
    {
        "id": "case_47",
        "description": "10 items: Weekend getaway expenses with conversational chatter",
        "text": "Fin de semana en la costa: hotel 65000, nafta 25000, peajes 6000, almuerzo sábado 18000, cena sábado 24000, desayuno domingo 7500, sombrilla 12000, almuerzo domingo 19000, café 3200 y helado 4500",
        "expected_count": 10,
        "expected_action": "log_transaction",
        "expected_amounts": [65000.0, 25000.0, 6000.0, 18000.0, 24000.0, 7500.0, 12000.0, 19000.0, 3200.0, 4500.0],
        "expected_types": ["expense"] * 10
    },
    {
        "id": "case_48",
        "description": "10 items: Mixed financial recap (4 incomes, 6 expenses)",
        "text": "Resumen: cobré 5000 sueldo, 800 freelance, 150 intereses, 300 devolución afip; y pagué 1500 tarjeta, 250 seguro auto, 120 celular, 450 supermercado, 80 combustible y 35 delivery",
        "expected_count": 10,
        "expected_action": "log_transaction",
        "expected_amounts": [5000.0, 800.0, 150.0, 300.0, 1500.0, 250.0, 120.0, 450.0, 80.0, 35.0],
        "expected_types": ["income", "income", "income", "income", "expense", "expense", "expense", "expense", "expense", "expense"]
    },

    # -------------------------------------------------------------
    # 11 TO 15 ITEMS SCENARIOS (49 to 55) - STRESS TESTING
    # -------------------------------------------------------------
    {
        "id": "case_49",
        "description": "11 items: Mixed shopping & income with chatter",
        "text": "Hola Clanomy! Te paso los movimientos: cobré 3200 de sueldo y 450 de comisiones. De gastos tuve: 450 super, 80 nafta, 35 estacionamiento, 120 cena, 15 propina, 60 farmacia, 25 taxi, 90 zapatillas y 40 cine",
        "expected_count": 11,
        "expected_action": "log_transaction",
        "expected_amounts": [3200.0, 450.0, 450.0, 80.0, 35.0, 120.0, 15.0, 60.0, 25.0, 90.0, 40.0],
        "expected_types": ["income", "income"] + ["expense"] * 9
    },
    {
        "id": "case_50",
        "description": "12 items: Birthday party event organisation expenses",
        "text": "Organización del cumple de Sofi: torta 18000, cotillón 12500, empanadas 28000, pizzas 22000, gaseosas 14000, cerveza 19000, hielo 3500, vasos descartables 2800, pelotero 35000, animadora 25000, souvenirs 9500 y delivery 3000",
        "expected_count": 12,
        "expected_action": "log_transaction",
        "expected_amounts": [18000.0, 12500.0, 28000.0, 22000.0, 14000.0, 19000.0, 3500.0, 2800.0, 35000.0, 25000.0, 9500.0, 3000.0],
        "expected_types": ["expense"] * 12
    },
    {
        "id": "case_51",
        "description": "12 items: English month start audit (3 incomes, 9 expenses)",
        "text": "Hey bot, new month audit: received 4200 paycheck, 350 freelance writing, 80 cashback. Paid out: 1400 mortgage, 120 electricity, 65 water, 85 internet, 45 mobile, 280 groceries, 60 gym, 35 streaming, and 50 pet food",
        "expected_count": 12,
        "expected_action": "log_transaction",
        "expected_amounts": [4200.0, 350.0, 80.0, 1400.0, 120.0, 65.0, 85.0, 45.0, 280.0, 60.0, 35.0, 50.0],
        "expected_types": ["income", "income", "income"] + ["expense"] * 9
    },
    {
        "id": "case_52",
        "description": "13 items: Winter holidays travel breakdown (2 incomes, 11 expenses)",
        "text": "Vacaciones de invierno: cobré 2500 de aguinaldo y 1000 de adelanto. Gasté: 45000 en pasajes, 85000 en cabaña, 12000 en excursión, 8500 en almuerzo, 14000 en cena, 3500 en café, 6000 en recuerdos, 4200 en chocolates, 9500 en combustible, 2500 en peajes y 1800 en propinas",
        "expected_count": 13,
        "expected_action": "log_transaction",
        "expected_amounts": [2500.0, 1000.0, 45000.0, 85000.0, 12000.0, 8500.0, 14000.0, 3500.0, 6000.0, 4200.0, 9500.0, 2500.0, 1800.0],
        "expected_types": ["income", "income"] + ["expense"] * 11
    },
    {
        "id": "case_53",
        "description": "14 items: Construction & hardware purchase items",
        "text": "Materiales de obra: cemento 45000, arena 22000, cal 14000, ladrillos 65000, hierro 52000, alambre 6500, clavos 3200, tablas 28000, flete 18000, hidrófugo 8500, viguetas 42000, ladrillones 31000, guantes 2500 y baldes 4000",
        "expected_count": 14,
        "expected_action": "log_transaction",
        "expected_amounts": [45000.0, 22000.0, 14000.0, 65000.0, 52000.0, 6500.0, 3200.0, 28000.0, 18000.0, 8500.0, 42000.0, 31000.0, 2500.0, 4000.0],
        "expected_types": ["expense"] * 14
    },
    {
        "id": "case_54",
        "description": "14 items: Family monthly budget recap (4 incomes, 10 expenses)",
        "text": "Reporte familiar: papá cobró 350000 de sueldo, mamá 280000 de honorarios, 45000 de jubilación abuela, 20000 de plazo fijo. Pagamos: alquiler 180000, expensas 45000, colegio 95000, obra social 68000, luz 14000, gas 6500, internet 11000, super 85000, nafta 32000 y farmacia 12500",
        "expected_count": 14,
        "expected_action": "log_transaction",
        "expected_amounts": [350000.0, 280000.0, 45000.0, 20000.0, 180000.0, 45000.0, 95000.0, 68000.0, 14000.0, 6500.0, 11000.0, 85000.0, 32000.0, 12500.0],
        "expected_types": ["income", "income", "income", "income"] + ["expense"] * 10
    },
    {
        "id": "case_55",
        "description": "15 items: Maximum stress test with mixed currencies, chatter, 5 incomes and 10 expenses",
        "text": "Buenas noches Clanomy! Te mando todo el cierre de quincena sin falta: me pagaron 2500 usd de cliente del exterior, 150000 pesos de sueldo local, 45000 pesos de horas extras, 300 usd de cripto y 25000 pesos que me devolvió Juan. Por el lado de gastos: pagué 120000 pesos de tarjeta visa, 450 usd de pasajes en cuotas, 18500 pesos de supermercado coto, 9200 pesos de combustible ypf, 3500 pesos en la verdulería de la esquina, gasté 12000 pesos en farmacia central, 2500 pesos en café starbucks, pagué 6500 de internet movistar, dejé 1500 pesos de propina y me compré una remera por 14000 pesos. Uff, qué quincena!",
        "expected_count": 15,
        "expected_action": "log_transaction",
        "expected_amounts": [2500.0, 150000.0, 45000.0, 300.0, 25000.0, 120000.0, 450.0, 18500.0, 9200.0, 3500.0, 12000.0, 2500.0, 6500.0, 1500.0, 14000.0],
        "expected_types": ["income", "income", "income", "income", "income"] + ["expense"] * 10
    }
]
