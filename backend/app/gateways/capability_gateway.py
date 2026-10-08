from decimal import Decimal

from app.seed.sample_data import ACCOUNTS, BENEFICIARIES


class ReadPrepareCapabilityGateway:
    def eligible_accounts(self):
        return [{"account_ref": key, **value, "synthetic": True} for key, value in ACCOUNTS.items()]

    def balance(self, account_ref: str):
        account = ACCOUNTS.get(account_ref)
        if not account:
            raise KeyError(account_ref)
        return {"account_ref": account_ref, **account, "synthetic": True}

    def prepare_transfer(self, amount: str, beneficiary: str):
        beneficiary_info = BENEFICIARIES.get(beneficiary.lower())
        if not beneficiary_info:
            beneficiary_info = f"{beneficiary} •••• 0000"
        return {
            "from_account": "SYN-1001 •••• 1001",
            "beneficiary": beneficiary_info,
            "amount": str(Decimal(amount)),
            "currency": "THB",
            "fee": "0.00",
            "execution_date": "Today",
            "synthetic": True,
        }

    def prepare_bill_payment(self):
        return {
            "from_account": "SYN-1001 •••• 1001",
            "beneficiary": BENEFICIARIES["electricity"],
            "amount": "2500.00",
            "currency": "THB",
            "fee": "0.00",
            "execution_date": "Today",
            "synthetic": True,
        }


capability_gateway = ReadPrepareCapabilityGateway()
