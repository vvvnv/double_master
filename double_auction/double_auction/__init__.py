from otree.api import *
import time
import random


doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 8
    ITEMS_PER_SELLER = 3
    ITEMS_PER_BUYER = 3
    TIME_FOR_PERIOD = 2*60
    TIME_FOR_PERIOD1 = 4*60

Constants = C

class Subsession(BaseSubsession):
    num_buyers = models.IntegerField()
    PRODUCTION_COSTS_MIN = models.CurrencyField()
    PRODUCTION_COSTS_MAX = models.CurrencyField()
    VALUATION_MIN = models.CurrencyField()
    VALUATION_MAX = models.CurrencyField()



def creating_session(subsession: Subsession):
    subsession.group_randomly()
    players = subsession.get_players()

    subsession.num_buyers = int(len(players) - 3) #число покупателей за исключением трех продавцов
    subsession.PRODUCTION_COSTS_MIN = cu(10)
    subsession.PRODUCTION_COSTS_MAX = cu(80)
    subsession.VALUATION_MIN = cu(50)
    subsession.VALUATION_MAX = cu(110)
           
    for p in players:
        # this means if the player's ID is not a multiple of 2, they are a buyer.
        # for more buyers, change the 2 to 3
        p.is_buyer = p.id_in_group <= subsession.num_buyers
        if p.is_buyer:
            p.num_items = 0
            p.break_even_point = random.randint(subsession.VALUATION_MIN, subsession.VALUATION_MAX)
            p.current_offer = 0
        else:
            p.num_items = C.ITEMS_PER_SELLER
            p.break_even_point = random.randint(subsession.PRODUCTION_COSTS_MIN, subsession.PRODUCTION_COSTS_MAX)
            p.current_offer = cu(200)

def vars_for_admin_report(subsession):
        series = []
        subs_avg = []
        # for subs in subsession.in_all_rounds():
        #     subs_avg.append(round(100*pl_coop_num/(pl_coop_num+pl_defect_num),1) if pl_coop_num+pl_defect_num>0 else float('nan'))


        for player in subsession.get_players():
            pl_id = player.participant.id_in_session
            name = player.participant.label
            pl_totalpay = sum(p.payoff for p in player.in_all_rounds())
            series.append(dict ( ID = pl_id, Name = name, TotalPay = pl_totalpay))
        cnt = len(series)
        if cnt>0:
            av = dict (ID = 0, Name = 'AVG', TotalPay = round(sum(s['TotalPay'] for s in series)/cnt,0) )
            series.insert(0,av)


        return dict( game_data=series, period_data = subs_avg, round_numbers=list(range(1, len(subs_avg) + 1)))


class Group(BaseGroup):
    start_timestamp = models.IntegerField()


class Player(BasePlayer):
    is_buyer = models.BooleanField()
    current_offer = models.CurrencyField()
    break_even_point = models.CurrencyField()
    msg = models.CurrencyField()
    num_items = models.IntegerField()


class Order(ExtraModel):
    group = models.Link(Group)
    trader = models.Link(Player)
    price = models.CurrencyField()
    buysell = models.IntegerField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")

class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Player)
    seller = models.Link(Player)
    price = models.CurrencyField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")


def custom_export(players):
    # Export an ExtraModel called "Trial"

    yield ['session', 'table', 'group', 'round_number', 'buyer', 'seller', 'price', 'seconds']

    # 'filter' without any args returns everything
    trials = Transaction.filter()
    for trial in trials:
        buyer = trial.buyer
        seller = trial.seller
        session = buyer.session
        group = trial.group

        yield [session.code, 'trades', group.id_in_subsession, buyer.round_number, buyer.participant.id_in_session, seller.participant.id_in_session, trial.price, trial.seconds]

    yield ['session', 'table', 'group', 'round_number', 'trader', 'direction', 'price', 'seconds']

    # 'filter' without any args returns everything
    trials = Order.filter()
    for trial in trials:
        trader = trial.trader
        session = buyer.session
        group = trial.group

        yield [session.code, 'orders', group.id_in_subsession, trader.round_number, trader.participant.id_in_session, trial.buysell, trial.price, trial.seconds]


def find_match(buyers, sellers):
    for buyer in buyers:
        for seller in sellers:
            if seller.num_items > 0 and buyer.num_items < C.ITEMS_PER_BUYER and seller.current_offer <= buyer.current_offer:
                # return as soon as we find a match (the rest of the loop will be skipped)
                return [buyer, seller]


def live_method(player: Player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    news = None
    if data:
        if player.is_buyer:
            if player.num_items >= C.ITEMS_PER_BUYER:
                player.current_offer = 0
                return
        else:
            if player.num_items == 0:
                player.current_offer = cu(200)
                return
        offer = int(data['offer'])
        player.current_offer = offer
        Order.create(
            group=group,
            trader=player,
            buysell=1 if player.is_buyer else -1,
            price=offer,
            seconds=int(time.time() - group.start_timestamp),
        )
        
        if player.is_buyer:
            match = find_match(buyers=[player], sellers=sellers)
        else:
            match = find_match(buyers=buyers, sellers=[player])
        if match:
            [buyer, seller] = match
            price = seller.current_offer if player.is_buyer else buyer.current_offer 
            Transaction.create(
                group=group,
                buyer=buyer,
                seller=seller,
                price=price,
                seconds=int(time.time() - group.start_timestamp),
            )
            buyer.num_items += 1
            seller.num_items -= 1
            buyer.payoff += buyer.break_even_point - price
            seller.payoff += price - seller.break_even_point
            buyer.current_offer = 0
            seller.current_offer = cu(200)
            news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price)

    bids = sorted([p.current_offer for p in buyers if p.current_offer > 0], reverse=True)
    asks = sorted([p.current_offer for p in sellers if p.current_offer < cu(200)])
    highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]

    return {
        p.id_in_group: dict(
            num_items=p.num_items,
            current_offer=p.current_offer,
            payoff=p.payoff,
            bids=bids,
            asks=asks,
            highcharts_series=highcharts_series,
            news=news,
        )
        for p in players
    }


# PAGES
class Introduction(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number==1

class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.start_timestamp = int(time.time())


class Trading(Page):
    live_method = live_method

    @staticmethod
    def js_vars(player: Player):
        return dict(id_in_group=player.id_in_group, is_buyer=player.is_buyer, buyer_num = C.ITEMS_PER_BUYER)

    @staticmethod
    def get_timeout_seconds(player: Player):
        import time

        group = player.group
        if player.round_number==1:
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
    def after_all_players_arrive(subsession:Subsession):
        subsession.session.vars['tot_res'] = vars_for_admin_report(subsession)

class TotalResult(Page):

    @staticmethod    
    def vars_for_template(player):
        return player.session.vars['tot_res']

    @staticmethod    
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS


page_sequence = [Introduction, WaitToStart,  Trading, ResultsWaitPage, Results, TotalResultWaitPage, TotalResult]
