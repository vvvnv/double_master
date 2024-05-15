from otree.api import *
import time
import random

doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction_v'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 2
    SELLER_NUM = 3  # Количество продавцов
    ITEMS_PER_SELLER = 3  # Количество товара для продажи
    ITEMS_PER_BUYER = 3  # Количесвто товаров для покупки
    TIME_FOR_PERIOD = 60 * 0.5
    TIME_FOR_PERIOD1 = 60 * 0.5
    MAX_VAL = 200
    FINE_CHOISE = [0, 5, 10]
    # extra_coef = 10
    COMPANY_NAMES = ['A', 'B', 'C']
    PROFIT_PER_CONTRACT = 2


Constants = C


def get_company_name(company_id):
    return C.COMPANY_NAMES[company_id - 1]


class Subsession(BaseSubsession):
    PRODUCTION_COSTS_MIN = models.IntegerField()
    PRODUCTION_COSTS_MAX = models.IntegerField()
    VALUATION_MIN = models.IntegerField()
    VALUATION_MAX = models.IntegerField()
    num_sellers = models.IntegerField()
    bad_id = models.IntegerField()


def creating_session(subsession: Subsession):
    subsession.group_randomly()
    subsession.PRODUCTION_COSTS_MIN = 10
    subsession.PRODUCTION_COSTS_MAX = 80
    subsession.VALUATION_MIN = 50
    subsession.VALUATION_MAX = 110
    subsession.num_sellers = C.SELLER_NUM

    for g in subsession.get_groups():
        init_group(g, False)
    for p in subsession.get_players():
        init_player(p)


def vars_for_admin_report(subsession):
    series = []
    subs_avg = []
    # for subs in subsession.in_all_rounds():
    #     subs_avg.append(round(100*pl_coop_num/(pl_coop_num+pl_defect_num),1) if pl_coop_num+pl_defect_num>0 else float('nan'))

    for player in subsession.get_players():
        pl_id = player.participant.id_in_session
        name = player.participant.label
        pl_totalpay = sum(p.payoff for p in player.in_all_rounds())
        series.append(dict(ID=pl_id, Name=name, TotalPay=pl_totalpay))
    cnt = len(series)
    if cnt > 0:
        av = dict(ID=0, Name='AVG', TotalPay=round(sum(s['TotalPay'] for s in series) / cnt, 0))
        series.insert(0, av)

    return dict(game_data=series, period_data=subs_avg, round_numbers=list(range(1, len(subs_avg) + 1)))


class Group(BaseGroup):
    start_timestamp = models.IntegerField()
    contract_12 = models.BooleanField()  # Соглашение между продавцами 1 и 2
    contract_13 = models.BooleanField()  # Соглашение между продавцами 1 и 3
    contract_23 = models.BooleanField()  # Соглашение между продавцами 2 и 3
    bad_company_num = models.IntegerField()


class Player(BasePlayer):
    is_buyer = models.BooleanField()  # True - покупатель, False - продавец
    is_bad = models.BooleanField()  # True - покупатель, False - продавец
    # break_even_point = models.CurrencyField()       # Ценность товара
    num_items_left = models.IntegerField()  # Оставшееся количество товаров на покупку/продажу
    num_items = models.IntegerField(initial=0)  # количество товаров купленное/проданное
    num_items_from_bad = models.IntegerField(initial=0)  # количество товаров купленное/проданное
    extra_charge_for_bad = models.CurrencyField()  # сколько дополнительно списать с покупателя если купил у плохой компании
    trade_vol = models.CurrencyField(initial=cu(0))  # выручка от продажи / расходы на покупку
    contracts_volume = models.IntegerField(initial=0)  # количество товаров учитываемое в дополнительных контрактах
    costs = models.CurrencyField(initial=cu(0))  # себестоимость продаж / выкупная стоимость купленных
    # bad_info = models.BooleanField()        #True у продавца - плохая компания, True упокупателя - он знает какая компания плохая
    # player_msg = models.StringField()       #Информация для игрока

    current_offer1 = models.CurrencyField(
        initial=cu(0))  # Предложение цены для продавца 1 / если продавец то для своего товара
    current_offer2 = models.CurrencyField(initial=cu(0))  # Предложение цены для продавца 2
    current_offer3 = models.CurrencyField(initial=cu(0))  # Предложение цены для продавца 3
    current_offer_time1 = models.FloatField(
        initial=0)  # Предложение цены для продавца 1 / если продавец то для своего товара
    current_offer_time2 = models.FloatField(initial=0)  # Предложение цены для продавца 2
    current_offer_time3 = models.FloatField(initial=0)  # Предложение цены для продавца 3
    sell_count_offer = models.IntegerField(initial=0)  # количество единиц товара на продажу по текущей заявке

    change_contract_12 = models.BooleanField(blank=True,
                                             initial=False)  # изменить соглашение с продавцом с минимальным id
    change_contract_13 = models.BooleanField(blank=True,
                                             initial=False)  # изменить соглашение с продавцом с максимальным id
    change_contract_23 = models.BooleanField(blank=True,
                                             initial=False)  # изменить соглашение с продавцом с максимальным id


def init_group(group: Group, keep_info_from_last=False):
    if keep_info_from_last and (group.round_number > 1):
        # копируем соглашения из прошлого раунда
        prev_group = group.in_round(group.round_number - 1)
        group.contract_12 = prev_group.contract_12
        group.contract_13 = prev_group.contract_13
        group.contract_23 = prev_group.contract_23
        group.bad_company_num = prev_group.bad_company_num
    else:
        # инициализируем соглашения по умолчанию - заключенными
        group.contract_12 = True
        group.contract_13 = True
        group.contract_23 = True
        # определяем номер плохой компании
        group.bad_company_num = int(random.randint(1, group.subsession.num_sellers))


def init_player(player: Player):
    subsession = player.subsession
    player.is_buyer = player.id_in_group > subsession.num_sellers
    group = player.group
    if player.is_buyer:
        random_list = [random.randint(subsession.VALUATION_MIN, subsession.VALUATION_MAX) for _ in
                       range(C.ITEMS_PER_BUYER)]
    else:
        random_list = [random.randint(subsession.PRODUCTION_COSTS_MIN, subsession.PRODUCTION_COSTS_MAX) for _ in
                       range(C.ITEMS_PER_SELLER)]
        player.current_offer1 = C.MAX_VAL
        player.is_bad = player.id_in_group == group.bad_company_num

    player.extra_charge_for_bad = random.choice(C.FINE_CHOISE)  # cu

    sorted_list = sorted(random_list, reverse=player.is_buyer)
    player.num_items_left = len(sorted_list)

    for i, v in enumerate(sorted_list):
        ItemsValues.create(
            group=group,
            trader=player,
            item_id=i,
            item_value=v
        )


def calc_profit_group(group: Group):
    players = group.get_players()
    sellers = players[:group.subsession.num_sellers]
    contracts = [['contract_12', (0, 1)], ['contract_13', (0, 2)], ['contract_23', (1, 2)]]
    for c in contracts:
        cur_state = getattr(group, c[0])
        num_change = sum(1 for pn in c[1] if getattr(sellers[pn], 'change_' + c[0]))
        if cur_state:
            if num_change > 0:
                cur_state = False
        else:
            if num_change == 2:
                cur_state = True
        setattr(group, c[0], cur_state)

        if cur_state:
            vol = sellers[c[1][0]].num_items + sellers[c[1][1]].num_items
            sellers[c[1][0]].contracts_volume += vol
            sellers[c[1][1]].contracts_volume += vol

    for p in players:
        calc_profit_player(p)


def calc_profit_player(player: Player):
    player.costs = sum(x.item_value for x in ItemsValues.filter(trader=player) if x.item_id < player.num_items)
    if player.is_buyer:
        player.payoff = player.costs - player.trade_vol - player.extra_charge_for_bad * player.num_items_from_bad
    else:
        player.payoff = player.trade_vol - player.costs + player.contracts_volume * C.PROFIT_PER_CONTRACT


class ItemsValues(ExtraModel):
    group = models.Link(Group)
    trader = models.Link(Player)
    item_id = models.IntegerField()
    item_value = models.CurrencyField()  # Ценность товара / затраты на производство


class Order(ExtraModel):
    group = models.Link(Group)
    trader = models.Link(Player)
    company_id = models.IntegerField()
    price = models.CurrencyField()
    quantity = models.IntegerField()
    buysell = models.IntegerField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")


class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Player)
    seller = models.Link(Player)
    company_id = models.IntegerField()
    price = models.CurrencyField()
    quantity = models.IntegerField()
    buysell = models.IntegerField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")
    id_bad_company = models.CurrencyField()
    fine = models.CurrencyField()
    # trad_with_bad = models.BooleanField()
    # extra = models.CurrencyField()


def custom_export(players):
    # Export an ExtraModel called "Trial"

    yield {'session', 'table', 'group', 'round_number', 'id_bad_company', 'buyer', 'seller', 'price', 'company_id', 'quantity', 'buysell',
           'fine', 'seconds'}

    # 'filter' without any args returns everything
    trials = Transaction.filter()
    for trial in trials:
        buyer = trial.buyer
        seller = trial.seller
        session = buyer.session
        group = trial.group

        yield [session.code, 'trades', group.id_in_subsession, buyer.round_number, trial.id_bad_company,
               buyer.participant.id_in_session,
               seller.participant.id_in_session, trial.price, trial.company_id, trial.quantity, trial.fine, trial.seconds]

    yield ['session', 'table', 'group', 'round_number', 'id_bad_company', 'buyer', 'seller', 'price', 'company_id', 'quantity', 'buysell',
           'fine', 'seconds']

    # 'filter' without any args returns everything
    trials = Order.filter()
    for trial in trials:
        trader = trial.trader
        session = trader.session
        group = trial.group

        yield [session.code, 'orders', group.id_in_subsession, trader.round_number, trader.participant.id_in_session,
               trial.buysell, trial.price, trial.seconds]


def find_match(buyers, sellers):
    for buyer in buyers:
        for seller in sellers:
            if seller.num_items > 0 and buyer.num_items < C.ITEMS_PER_BUYER \
                    and ((seller.id_seller == 1 and seller.current_offer <= buyer.current_offer1)
                         or (seller.id_seller == 2 and seller.current_offer <= buyer.current_offer2)
                         or (seller.id_seller == 3 and seller.current_offer <= buyer.current_offer3)):
                # return as soon as we find a match (the rest of the loop will be skipped)
                return [buyer, seller]


def get_company_by_id(group, id):
    return group.get_player_by_id(id)


def get_player_quote_time(player, id):
    return getattr(player, 'current_offer_time' + str(id))


def get_player_quote_market(player, id):
    return getattr(player, 'current_offer' + str(id))


def set_player_quote_market(player, id, val):
    setattr(player, 'current_offer_time' + str(id), time.time())
    setattr(player, 'current_offer' + str(id), val)


def process_transaction(buyer, seller, c_id, price, quantity, buysell, news):
    group = buyer.group
    set_player_quote_market(buyer, c_id, 0)
    seller.sell_count_offer -= quantity
    Transaction.create(
        group=group,
        buyer=buyer,
        seller=seller,
        price=price,
        company_id=c_id,
        quantity=quantity,
        buysell=buysell,
        seconds=int(time.time() - group.start_timestamp),
    )
    buyer.num_items += quantity
    seller.num_items += quantity
    buyer.num_items_left -= quantity
    seller.num_items_left -= quantity
    buyer.trade_vol += price * quantity
    seller.trade_vol += price * quantity
    if seller.is_bad:
        buyer.num_items_from_bad += quantity
    if buyer.id_in_group in news:
        news[buyer.id_in_group]['price'] = (news[buyer.id_in_group]['price'] * news[buyer.id_in_group][
            'quantity'] + price * quantity) / (news[buyer.id_in_group]['quantity'] + quantity)
        news[buyer.id_in_group]['quantity'] += quantity
    else:
        news[buyer.id_in_group] = {'price': price, 'quantity': quantity}
    if seller.id_in_group in news:
        news[seller.id_in_group]['price'] = (news[seller.id_in_group]['price'] * news[seller.id_in_group][
            'quantity'] + price * quantity) / (news[seller.id_in_group]['quantity'] + quantity)
        news[seller.id_in_group]['quantity'] += quantity
    else:
        news[seller.id_in_group] = {'price': price, 'quantity': quantity}


def live_method(player, data):
    group = player.group
    players = group.get_players()
    news = {}
    id_bad_company = group.bad_company_num
    extra = 0
    if data:
        if 'field' in data:
            print(data['value'])
            setattr(player, data['field'], int(data['value']) == 1)
            return None
        # format: 
        # 'offer': цена в копейках/центах
        # 'company_id': номер рынка = номер продавца
        # 'qnt': количество товаров на продажу/покупку
        offer_price = int(data['offer']) / 100
        c_id = int(data['company_id'])
        quantity = int(data['quantity'])
        # сохранить заявку
        Order.create(
            group=group,
            trader=player,
            buysell=1 if player.is_buyer else -1,
            company_id=c_id,
            price=offer_price,
            quantity=quantity,
            seconds=int(time.time() - group.start_timestamp),
        )
        if player.is_buyer:
            buyer = player
            if quantity > 0:
                set_player_quote_market(buyer, c_id, offer_price)
                seller = players[c_id - 1]
                if (seller.current_offer1 <= offer_price) and (seller.sell_count_offer > 0):
                    price = seller.current_offer1
                    deal_vol = min(seller.sell_count_offer, quantity)
                    quantity -= deal_vol
                    process_transaction(buyer, seller, c_id, price, deal_vol, 1, news)
            else:
                set_player_quote_market(buyer, c_id, 0)
        else:
            seller = player
            c_id = player.id_in_group
            seller.sell_count_offer = quantity
            seller.current_offer1 = offer_price
            if quantity > 0:
                buyer_quotes = [[get_player_quote_market(p, c_id), get_player_quote_time(p, c_id), p] for p in players
                                if p.is_buyer]
                buyer_quotes.sort(key=lambda x: (-x[0], x[1]))
                for b in buyer_quotes:
                    if offer_price > b[0]:
                        break
                    process_transaction(b[2], seller, c_id, b[0], 1, -1, news)
                    if seller.sell_count_offer <= 0:
                        break

    bids = [sorted([[get_player_quote_market(p, i), 1] for p in players[3:] if get_player_quote_market(p, i) > 0],
                   reverse=True) for i in range(1, 4)]
    asks = [([[p.current_offer1, p.sell_count_offer]] if p.sell_count_offer > 0 else []) for p in players[:3]]
    highcharts_series = [[[tx.seconds, tx.price] for tx in Transaction.filter(group=group, company_id=i)] for i in
                         range(1, 4)]

    return {
        p.id_in_group: dict(
            num_items=p.num_items,
            num_items_left=p.num_items_left,
            current_offer1=p.current_offer1,
            current_offer2=p.current_offer2,
            current_offer3=p.current_offer3,
            sell_count_offer=p.sell_count_offer,
            #    payoff=p.payoff,
            bids=bids,
            asks=asks,
            highcharts_series=highcharts_series,
            news=news.get(p.id_in_group, None),
        )
        for p in players
    }


# PAGES
class Introduction(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.start_timestamp = int(time.time())


class Trading(Page):
    form_model = 'player'

    @staticmethod
    def get_form_fields(player):
        if player.is_buyer:
            return []
        else:
            return {1: ['change_contract_13', 'change_contract_12'],
                    2: ['change_contract_12', 'change_contract_23'],
                    3: ['change_contract_13', 'change_contract_23']}[player.id_in_group]

    live_method = live_method

    @staticmethod
    def js_vars(player: Player):
        return dict(id_in_group=player.id_in_group, is_buyer=player.is_buyer, buyer_num=C.ITEMS_PER_BUYER)

    @staticmethod
    def vars_for_template(player):
        return {'name': (get_company_name(player.id_in_group) if not player.is_buyer else ''),
                'player_msg': 'плохая компания: ' + get_company_name(player.group.bad_company_num),
                'item_vals': {(i + 1): itm.item_value for i, itm in enumerate(ItemsValues.filter(trader=player))}}

    @staticmethod
    def get_timeout_seconds(player: Player):
        import time

        group = player.group
        if player.round_number == 1:
            return (group.start_timestamp + C.TIME_FOR_PERIOD1) - time.time()
        else:
            return (group.start_timestamp + C.TIME_FOR_PERIOD) - time.time()


class ResultsWaitPage(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        calc_profit_group(group)


class Results(Page):
    timeout_seconds = 20


class TotalResultWaitPage(WaitPage):
    title_text = "Пожалуйста, подождите"
    body_text = "Ожидание финальных результатов."
    wait_for_all_groups = True

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def after_all_players_arrive(subsession: Subsession):
        subsession.session.vars['tot_res'] = vars_for_admin_report(subsession)


class TotalResult(Page):

    @staticmethod
    def vars_for_template(player):
        return player.session.vars['tot_res']

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS


page_sequence = [Introduction, WaitToStart, Trading, ResultsWaitPage, Results, TotalResultWaitPage, TotalResult]
