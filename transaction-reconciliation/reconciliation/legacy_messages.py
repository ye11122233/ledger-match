"""Render stored messages from the original build without modifying evidence."""

LEGACY_MESSAGES = {' 不能为空': ' is required',
 'amount 不能为空': 'amount is required',
 'currency 不能为空': 'currency is required',
 'transaction_date 不能为空': 'transaction_date is required',
 'transaction_id 不能为空': 'transaction_id is required',
 '交易编号、币种和金额一致': 'Transaction ID, currency and amount match',
 '交易编号最多 128 字符，且不能包含控制字符': 'Transaction ID must be at most 128 characters and contain no control '
                            'characters',
 '内部系统没有可匹配的交易': 'No matching transaction in the internal records',
 '同一交易编号和币种的金额不同': 'Amounts differ for the same transaction ID and currency',
 '同一来源的交易编号和币种重复；该键全部记录隔离': 'Duplicate transaction ID and currency within one source; all records '
                            'for this key are isolated',
 '币种仅支持 GBP、EUR、USD': 'Currency must be GBP, EUR or USD',
 '支付平台没有可匹配的交易': 'No matching transaction in the payment-platform records',
 '日期必须是有效的 YYYY-MM-DD': 'Date must be a valid YYYY-MM-DD calendar date',
 '金额须大于 0、最多两位小数且不超过 999999999.99': 'Amount must be positive, have at most two decimal places and '
                                    'not exceed 999999999.99',
 '；': '; ',
 '；发现相同编号的其他币种记录，请检查币种': '; The same transaction ID appears in other currencies; check the '
                         'currency'}


def english_message(message):
    for original, replacement in sorted(LEGACY_MESSAGES.items(), key=lambda pair: -len(pair[0])):
        message = message.replace(original, replacement)
    return message
