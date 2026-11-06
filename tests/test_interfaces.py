import pytest

from mpo_ev.instances import load_base, make_config
from mpo_ev.interfaces import Config, Instance, Product, Request


@pytest.fixture
def config():
    return make_config(4, 96, 19.0, load_base())  # sloty po 6 h, kroky po 15 min


def test_product_slots_and_validation():
    assert list(Product(1, 3).slots()) == [1, 2, 3]
    with pytest.raises(ValueError):
        Product(2, 1)


def test_config_lengths(config):
    assert config.slot_length_h == 6.0
    assert config.duration_h(Product(1, 2)) == 12.0


def test_lambda_must_fit_into_steps():
    with pytest.raises(ValueError):
        Config(4, 10, 3, 11.0, (1.0,))


def test_slot_stays_sellable_until_its_end(config):
    afternoon = Product(2, 3)  # začína 12:00
    assert config.is_sellable(afternoon, 50)  # 12:30, ako na obr. 3 článku
    assert config.is_sellable(afternoon, 71)  # krok 17:45-18:00
    assert not config.is_sellable(afternoon, 72)
    assert config.last_sale_step(Product(3, 3)) == 95


def test_last_sale_step_when_steps_do_not_align_with_slots():
    config = Config(24, 610, 3, 76.28, (1.0,))
    product = Product(0, 0)  # T_p = 1 h, teda 25,41 kroku
    assert config.last_sale_step(product) == 24


def test_instance_rejects_unordered_steps(config):
    a = Request(5, Product(0, 0), 1.0)
    b = Request(5, Product(1, 1), 1.0)
    with pytest.raises(ValueError):
        Instance(config, (a, b), seed=0)
