"""Invalid source values and budget configuration must have explicit outcomes."""
import pandas as pd
import pytest
from wallet.aggregator import load_wallet, load_wallets
from wallet.alerts import check_alerts


def write_csv(tmp_path, content):
    path = tmp_path / 'sample.csv'
    path.write_text(content)
    return str(path)


def test_whitespace_headers_are_normalized(tmp_path):
    df = load_wallet(write_csv(tmp_path, ' Date , DESCRIPTION , montant , compte \n2026-01-01,Courses,-10,courant\n'))
    assert df.iloc[0]['montant'] == -10


@pytest.mark.parametrize('amount', ['inf', '-inf', 'NaN'])
def test_nonfinite_amounts_are_excluded(tmp_path, amount):
    df = load_wallet(write_csv(tmp_path, f'date,description,montant,compte\n2026-01-01,Achat,{amount},courant\n2026-01-02,Achat,-10,courant\n'))
    assert df['montant'].tolist() == [-10]


@pytest.mark.parametrize('row', ['2026-01-01,,-10,courant', '2026-01-01,Achat,-10,', '2026-01-01,Achat,-10,TOTAL'])
def test_missing_or_reserved_account_data_is_rejected(tmp_path, row):
    with pytest.raises(ValueError):
        load_wallet(write_csv(tmp_path, 'date,description,montant,compte\n' + row + '\n'))


def test_all_invalid_file_does_not_produce_success(tmp_path):
    write_csv(tmp_path, 'date,description,montant,compte\ninvalid,Achat,-10,courant\n')
    with pytest.raises(ValueError, match='Aucun fichier valide'):
        load_wallets(str(tmp_path))


def test_zero_budget_produces_critical_alert():
    df = pd.DataFrame({'date': pd.to_datetime(['2026-01-01']), 'description':['Courses'], 'montant':[-10], 'compte':['courant'], 'categorie':['courses']})
    alerts = check_alerts(df, budget_limits={'courses': 0})
    budget = next(alert for alert in alerts if alert.type == 'budget_depasse')
    assert budget.severity == 'critical'
    assert 'budget nul' in budget.message


@pytest.mark.parametrize('kwargs', [{'budget_limits':{'courses':-1}}, {'budget_limits':{'courses':float('inf')}}, {'outlier_zscore':0}, {'divers_threshold':1.1}, {'min_balance':float('nan')}])
def test_bad_thresholds_raise_explicit_error(kwargs):
    with pytest.raises(ValueError):
        check_alerts(pd.DataFrame(), **kwargs)
