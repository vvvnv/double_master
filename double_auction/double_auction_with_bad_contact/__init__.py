from otree.api import *
import time
import random

doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 2
    ITEMS_PER_SELLER = 3  # Количество товара для продажи
    ITEMS_PER_BUYER = 3  # Количесвто товаров для покупки
    TIME_FOR_PERIOD = 5
    TIME_FOR_PERIOD1 = 20
    fine_choice = [0, 5, 10]
    extra_coef = 10


Constants = C


class Subsession(BaseSubsession):
    PRODUCTION_COSTS_MIN = models.CurrencyField()
    PRODUCTION_COSTS_MAX = models.CurrencyField()
    VALUATION_MIN = models.CurrencyField()
    VALUATION_MAX = models.CurrencyField()
    num_seller = models.IntegerField()
    bad_id = models.CurrencyField()


def creating_session(subsession: Subsession):
    # subsession.group_randomly()
    players = subsession.get_players()

    subsession.PRODUCTION_COSTS_MIN = cu(10)
    subsession.PRODUCTION_COSTS_MAX = cu(80)
    subsession.VALUATION_MIN = cu(50)
    subsession.VALUATION_MAX = cu(110)
    subsession.num_seller = cu(3)

    for p in players:
        # this means if the player's ID is not a multiple of 2, they are a buyer.
        # for more buyers, change the 2 to 3
        p.is_buyer = p.id_in_group >= subsession.num_seller
        if p.is_buyer:
            p.num_items = 0
            p.break_even_point = random.randint(subsession.VALUATION_MIN, subsession.VALUATION_MAX)
            if (p.id_in_group == len(players)) or (p.id_in_group == len(players) - 1):
                p.player_msg = f"Bad company is {subsession.bad_id}"
                p.bad_info = True
            else:
                p.player_msg = ""
                p.bad_info = False
        else:
            p.num_items = C.ITEMS_PER_SELLER
            p.id_seller = p.id_in_group
            p.break_even_point = random.randint(subsession.PRODUCTION_COSTS_MIN, subsession.PRODUCTION_COSTS_MAX)
            if p.id_in_group in subsession.bad_id:
                p.bad_info = True
                p.player_msg = "You are a bad company"
            else:
                p.bad_info = False
                p.player_msg = "You are NOT a bad company"
            p.seller_x = random.randint(1, subsession.num_seller) != p.id_seller  # todo
            p.seller_y = random.randint(1, subsession.num_seller) != p.id_seller != p.seller_x
            p.contact_x = False
            p.contact_y = False
            p.bad_conact = False


def create_round(subsession):
    print('session id', id(subsession.session))

    if subsession.round_number == 1:
        subsession.bad_id = [int(random.randint(1, subsession.num_seller))]
    else:
        pass


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


class Player(BasePlayer):
    is_buyer = models.BooleanField()  # True - покупатель, False - продавец
    break_even_point = models.CurrencyField()  # Ценность товара
    num_items = models.IntegerField()  # Количество товаров
    bad_info = models.BooleanField()  # True у продавца - плохая компания, True у покупателя - он знает какая компания плохая
    player_msg = models.StringField()  # Информация для игрока


class Buyer(Player):
    current_offer1 = models.CurrencyField()  # Предложение цены для продавца 1
    current_offer2 = models.CurrencyField()  # Предложение цены для продавца 2
    current_offer3 = models.CurrencyField()  # Предложение цены для продавца 3


class Seller(Player):
    id_seller = models.IntegerField()  # Id продавца
    current_offer = models.CurrencyField()  # Предложение цены для своего товара
    seller_x = models.IntegerField()  # Id продавца х
    seller_y = models.IntegerField()  # Id продавца у
    contact_x = models.BooleanField()  # Соглашение с продавцом х
    contact_y = models.BooleanField()  # Соглашение с продавцом у
    bad_contact = models.BooleanField()  # Соглашение с плохим продавцом


class Order(ExtraModel):
    group = models.Link(Group)
    trader = models.Link(Player)
    company_id = models.CurrencyField()
    price = models.CurrencyField()
    buysell = models.IntegerField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")


class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Buyer)
    seller = models.Link(Seller)
    price = models.CurrencyField()
    id_bad_company = models.CurrencyField()
    seller_contact_x = models.BooleanField()
    seller_contact_y = models.BooleanField()
    x_id = models.CurrencyField()
    y_id = models.CurrencyField()
    fine = models.CurrencyField()
    trade_with_bad = models.BooleanField()
    extra = models.CurrencyField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")


def custom_export(players):
    # Export an ExtraModel called "Trial"

    yield {'session', 'table', 'group', 'round_number', 'id_bad_company', 'buyer', 'seller', 'price',
           'seller_contact_x', 'seller_contact_y', 'x_id', 'y_id', 'fine', 'trade_with_bad', 'extra', 'seconds'}

    # 'filter' without any args returns everything
    trials = Transaction.filter()
    for trial in trials:
        buyer = trial.buyer
        seller = trial.seller
        session = buyer.session
        group = trial.group

        yield [session.code, 'trades', group.id_in_subsession, buyer.round_number, trial.id_bad_company,
               buyer.participant.id_in_session,
               seller.participant.id_in_session, trial.price, seller.contact_x, seller.contact_y,
               seller.seller_x, seller.seller_y, trial.fine, trial.trade_with_bad, trial.extra, trial.seconds]

    yield ['session', 'table', 'group', 'round_number', 'id_bad_company', 'trader', 'direction', 'price',
           'seller_contact_x', 'seller_contact_y', 'x_id', 'y_id', 'fine', 'trade_with_bad', 'extra', 'se conds']

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


def live_method(player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    sellers_dict = {s.id_seller: s for s in sellers}
    news = None
    id_bad_company = Subsession.bad_id
    extra = 0
    order_needed = True
    if data:
        if player.is_buyer:
            if player.num_items >= C.ITEMS_PER_BUYER:
                player.current_offer1 = 0
                player.current_offer2 = 0
                player.current_offer3 = 0
                order_needed = False
            else:
                offer1 = int(data['offer1'])
                offer2 = int(data['offer2'])
                offer3 = int(data['offer3'])
                if offer1 != 0:
                    offer_price = offer1
                    c_id = 1
                elif offer2 != 0:
                    offer_price = offer2
                    c_id = 2
                else:
                    offer_price = offer3
                    c_id = 3
                player.current_offer1 = offer1
                player.current_offer2 = offer2
                player.current_offer3 = offer3

        else:
            offer_price = int(data['offer'])
            player.contact_x = bool(data['contact_x'])
            player.contact_y = bool(data['contact_y'])
            player.current_offer = offer_price
            c_id = player.id_seller
            if player.num_items == 0:
                player.current_offer = cu(200)
        if order_needed:
            Order.create(
                group=group,
                trader=player,
                buysell=1 if player.is_buyer else -1,
                company_id=c_id,
                price=offer_price,
                seconds=int(time.time() - group.start_timestamp),
            )
        if player.is_buyer:
            match = find_match(buyers=[player], sellers=sellers)
        else:
            match = find_match(buyers=buyers, sellers=[player])
        if match:
            [buyer, seller] = match
            trade_with_bad = seller.bad_info
            fine = random.choice(C.fine_choice) if trade_with_bad else 0
            price = seller.current_offer if player.is_buyer else max(buyer.current_offer1,  # fixme (pick c_id)
                                                                     buyer.current_offer2,  # fixme todo
                                                                     buyer.current_offer3)
            if seller.contact_x:
                contragent = sellers_dict[seller.seller_x]
                if contragent.seller_x == seller.id_seller and contragent.contact_x \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y:
                    seller.payoff += C.extra_coef
                    contragent.payoff += C.extra_coef
                    extra = C.extra_coef
                    if seller.bad_info or contragent.bad_info:
                        Subsession.bad_id.extend(seller.id_seller, contragent.id_seller)
                elif contragent.seller_x == seller.id_seller and contragent.contact_x is False \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y is False:
                    if seller.bad_info:
                        Subsession.bad_id.remove(contragent.id_seller)
                    elif contragent.bad_info:
                        Subsession.bad_id.remove(seller.id_seller)

            if seller.contact_y:
                contragent = sellers_dict[seller.seller_y]
                if contragent.seller_x == seller.id_seller and contragent.contact_x \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y:
                    seller.payoff += C.extra_coef
                    contragent.payoff += C.extra_coef
                    extra = C.extra_coef
                    if seller.bad_info or contragent.bad_info:
                        subsession.bad_id.extend(seller.id_seller, contragent.id_seller)
                elif contragent.seller_y == seller.id_seller and contragent.contact_x == False \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y == False:
                    if seller.bad_info:
                        subsession.bad_id.remove(contragent.id_seller)
                    elif contragent.bad_info:
                        subsession.bad_id.remove(seller.id_seller)

            Transaction.create(
                group=group,
                id_bad_company=id_bad_company,
                buyer=buyer,
                seller=seller,
                price=price,
                fine=fine,
                seller_contact_x=seller.contact_x,
                seller_contact_y=seller.contact_y,
                x_id=seller.seller_x,
                y_id=seller.seller_y,
                trade_with_bad=trade_with_bad,
                extra=extra,
                seconds=int(time.time() - group.start_timestamp),
            )
            buyer.num_items += 1
            seller.num_items -= 1
            buyer.payoff += buyer.break_even_point - price - fine
            seller.payoff += price - seller.break_even_point
            buyer.current_offer = 0
            seller.current_offer = cu(200)
            extra = 0
            news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price, fine=fine)

    # bids = sorted([p.current_offer for p in buyers if p.current_offer > 0], reverse=True)
    # asks = sorted([p.current_offer for p in sellers if p.current_offer < cu(200)])
    # highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]


#
# return {
#    p.id_in_group: dict(
#        num_items=p.num_items,
#        current_offer=p.current_offer,
#        payoff=p.payoff,
#        bids=bids,
#        asks=asks,
#        highcharts_series=highcharts_series,
#        news=news,
#    )
#    for p in players
# }

def live_method(player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    sellers_dict = {s.id_seller: s for s in sellers}
    news = None
    id_bad_company = Subsession.bad_id
    extra = 0
    order_needed = True
    if data:
        if player.is_buyer:
            if player.num_items >= C.ITEMS_PER_BUYER:
                player.current_offer1 = 0
                player.current_offer2 = 0
                player.current_offer3 = 0
                order_needed = False
            else:
                offer1 = int(data['offer1'])
                offer2 = int(data['offer2'])
                offer3 = int(data['offer3'])
                if offer1 != 0:
                    offer_price = offer1
                    c_id = 1
                elif offer2 != 0:
                    offer_price = offer2
                    c_id = 2
                else:
                    offer_price = offer3
                    c_id = 3
                player.current_offer1 = offer1
                player.current_offer2 = offer2
                player.current_offer3 = offer3

        else:
            offer_price = int(data['offer'])
            player.contact_x = bool(data['contact_x'])
            player.contact_y = bool(data['contact_y'])
            player.current_offer = offer_price
            c_id = player.id_seller
            if player.num_items == 0:
                player.current_offer = cu(200)
        if order_needed:
            Order.create(
                group=group,
                trader=player,
                buysell=1 if player.is_buyer else -1,
                company_id=c_id,
                price=offer_price,
                seconds=int(time.time() - group.start_timestamp),
            )
        if player.is_buyer:
            match = find_match(buyers=[player], sellers=sellers)
        else:
            match = find_match(buyers=buyers, sellers=[player])
        if match:
            [buyer, seller] = match
            trade_with_bad = seller.bad_info
            fine = random.choice(C.fine_choice) if trade_with_bad else 0
            price = seller.current_offer if player.is_buyer else max(buyer.current_offer1,  # fixme (pick c_id)
                                                                     buyer.current_offer2,  # fixme todo
                                                                     buyer.current_offer3)
            if seller.contact_x:
                contragent = sellers_dict[seller.seller_x]
                if contragent.seller_x == seller.id_seller and contragent.contact_x \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y:
                    seller.payoff += C.extra_coef
                    contragent.payoff += C.extra_coef
                    extra = C.extra_coef

            if seller.contact_y:
                contragent = sellers_dict[seller.seller_y]
                if contragent.seller_x == seller.id_seller and contragent.contact_x \
                        or contragent.seller_y == seller.id_seller and contragent.contact_y:
                    seller.payoff += C.extra_coef
                    contragent.payoff += C.extra_coef
                    extra = C.extra_coef
            Transaction.create(
                group=group,
                id_bad_company=id_bad_company,
                buyer=buyer,
                seller=seller,
                price=price,
                fine=fine,
                seller_contact_x=seller.contact_x,
                seller_contact_y=seller.contact_y,
                x_id=seller.seller_x,
                y_id=seller.seller_y,
                trade_with_bad=trade_with_bad,
                extra=extra,
                seconds=int(time.time() - group.start_timestamp),
            )
            buyer.num_items += 1
            seller.num_items -= 1
            buyer.payoff += buyer.break_even_point - price - fine
            seller.payoff += price - seller.break_even_point
            buyer.current_offer = 0
            seller.current_offer = cu(200)
            extra = 0
            news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price, fine=fine)

    # bids = sorted([p.current_offer for p in buyers if p.current_offer > 0], reverse=True)
    # asks = sorted([p.current_offer for p in sellers if p.current_offer < cu(200)])
    # highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]


#
# return {
#    p.id_in_group: dict(
#        num_items=p.num_items,
#        current_offer=p.current_offer,
#        payoff=p.payoff,
#        bids=bids,
#        asks=asks,
#        highcharts_series=highcharts_series,
#        news=news,
#    )
#    for p in players
# }
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
    live_method = live_method

    @staticmethod
    def js_vars(player: Player):
        return dict(id_in_group=player.id_in_group, is_buyer=player.is_buyer, buyer_num=C.ITEMS_PER_BUYER)

    @staticmethod
    def get_timeout_seconds(player: Player):
        import time

        group = player.group
        if player.round_number == 1:
            return (group.start_timestamp + C.TIME_FOR_PERIOD1) - time.time()
        else:
            return (group.start_timestamp + C.TIME_FOR_PERIOD) - time.time()


class ResultsWaitPage(WaitPage):
    pass


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
