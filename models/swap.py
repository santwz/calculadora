from .leg import SwapLeg

class Swap:
    def __init__(self, leg_long: SwapLeg, leg_short: SwapLeg):
        """
        leg_long: The receiving leg (Ativo/Comprada)
        leg_short: The paying leg (Passivo/Vendida)
        """
        self.leg_long = leg_long
        self.leg_short = leg_short

    def calculate_net_value(self, calendar):
        fv_long = self.leg_long.calculate_future_value(calendar)
        fv_short = self.leg_short.calculate_future_value(calendar)
        
        # In a typical swap, the value is the difference between the two legs' final values
        # adjusted to PV, but here we are calculating Final Settlement Value (Ajuste).
        # We'll return both FV and the Net (Long - Short).
        
        return {
            "fv_long": fv_long,
            "fv_short": fv_short,
            "net_value": fv_long - fv_short,
            "flow_long": fv_long - self.leg_long.calculate_initial_value(),
            "flow_short": fv_short - self.leg_short.calculate_initial_value()
        }
