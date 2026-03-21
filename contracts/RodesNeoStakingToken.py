from typing import Any, cast
from boa3.builtin.compile_time import public, NeoMetadata
from boa3.builtin.interop import runtime, storage
from boa3.builtin.interop.blockchain import Transaction
from boa3.builtin.type import UInt160
from boa3.builtin.contract import Nep17TransferEvent, abort
from boa3.builtin.interop.contract import call_contract
from boa3.builtin.interop.neo import NeoToken, GasToken

TOKEN_SYMBOL = 'RNST'
TOKEN_DECIMALS = 8
TOKEN_TOTAL_SUPPLY = 100_000_000 * 10 ** TOKEN_DECIMALS

STAKED_PREFIX = b'staked_'
LAST_CLAIM_PREFIX = b'lastclaim_'
REWARD_RATE_KEY = b'rewardrate'
TOTAL_STAKED_KEY = b'totalstaked'
DEFAULT_REWARD_RATE = 10  # 0.1% per day

def get_staked(account: UInt160) -> int:
    return storage.get_int(STAKED_PREFIX + account)

def get_last_claim(account: UInt160) -> int:
    return storage.get_int(LAST_CLAIM_PREFIX + account)

def get_reward_rate() -> int:
    rate = storage.get_int(REWARD_RATE_KEY)
    return rate if rate > 0 else DEFAULT_REWARD_RATE

def get_total_staked() -> int:
    return storage.get_int(TOTAL_STAKED_KEY)

@public(safe=True)
def symbol() -> str:
    return TOKEN_SYMBOL

@public(safe=True)
def decimals() -> int:
    return TOKEN_DECIMALS

@public(name='totalSupply', safe=True)
def total_supply() -> int:
    return storage.get_int(b'totalSupply')

@public(name='balanceOf', safe=True)
def balance_of(account: UInt160) -> int:
    return storage.get_int(account)

@public
def transfer(from_address: UInt160, to_address: UInt160, amount: int, data: Any) -> bool:
    if len(from_address) != 20 or len(to_address) != 20 or amount < 0:
        return False
    from_balance = balance_of(from_address)
    if from_balance < amount:
        return False
    if from_address != to_address and amount != 0:
        storage.put_int(from_address, from_balance - amount)
        storage.put_int(to_address, balance_of(to_address) + amount)
    Nep17TransferEvent(from_address, to_address, amount)
    if runtime.get_contract(to_address) is not None:
        call_contract(to_address, 'onNEP17Payment', [from_address, amount, data])
    return True

@public
def onNEP17Payment(from_address: UInt160, amount: int, data: Any):
    if runtime.calling_script_hash == runtime.executing_script_hash:
        do_stake(from_address, amount)
    elif runtime.calling_script_hash == NeoToken.hash or runtime.calling_script_hash == GasToken.hash:
        # Mint logic for initial supply
        pass

def do_stake(account: UInt160, amount: int):
    staked = get_staked(account)
    storage.put_int(STAKED_PREFIX + account, staked + amount)
    storage.put_int(TOTAL_STAKED_KEY, get_total_staked() + amount)
    if get_last_claim(account) == 0:
        storage.put_int(LAST_CLAIM_PREFIX + account, runtime.get_time())

@public
def claim(account: UInt160) -> int:
    if not runtime.check_witness(account):
        return 0
    staked = get_staked(account)
    if staked == 0:
        return 0
    last = get_last_claim(account)
    now = runtime.get_time()
    seconds = now - last if now > last else 0
    rewards = (seconds * get_reward_rate() * staked) // (86400 * 10000)
    if rewards > 0:
        # Mint rewards (simplified - add mint logic in production)
        storage.put_int(LAST_CLAIM_PREFIX + account, now)
    return rewards

@public
def unstake(account: UInt160, amount: int):
    if not runtime.check_witness(account):
        return
    staked = get_staked(account)
    if staked < amount:
        return
    storage.put_int(STAKED_PREFIX + account, staked - amount)
    storage.put_int(TOTAL_STAKED_KEY, get_total_staked() - amount)
    transfer(runtime.executing_script_hash, account, amount, None)

@public
def set_reward_rate(new_rate: int):
    if not runtime.check_witness(runtime.executing_script_hash):  # owner logic simplified
        return
    storage.put_int(REWARD_RATE_KEY, new_rate)

@public
def _deploy(data: Any, update: bool):
    if not update:
        container = runtime.script_container
        storage.put_int(b'totalSupply', TOKEN_TOTAL_SUPPLY)
        storage.put_int(REWARD_RATE_KEY, DEFAULT_REWARD_RATE)
        storage.put_int(container.sender, TOKEN_TOTAL_SUPPLY)

@public
def manifest_metadata() -> NeoMetadata:
    meta = NeoMetadata()
    meta.name = "RodesNeoStakingToken"
    meta.supported_standards = ['NEP-17']
    meta.author = "Crypto Neoboy (@Rodes_Neo)"
    meta.description = "RNST - Easy Staking Token with Automatic Daily Rewards for Neo Smart Savings Vault"
    return meta
