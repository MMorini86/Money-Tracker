import os
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
    abort, render_template, flash
import time
from calendar import monthrange
import requests
from bs4 import BeautifulSoup
import re
import datetime


app = Flask(__name__)
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'mt.db'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def gbp_on_euro():  # check on a website current currency change
    s = requests.session()
    html = s.get('https://it.finance.yahoo.com/valute/euro')
    soup = BeautifulSoup(html.text, "lxml")
    for l in soup.findAll("td" , { "class" : "col1" }):
        if l.text.find('EUR/GBP') != -1:
            val = l.next_siblings
    next(val)
    a = next(val).text
    try:
        gbp = float(a.replace(',', '.'))
    except ValueError:
            print('')
    s.close()
    return gbp
GBP = gbp_on_euro()


def month_string_to_number(string):
    m = {
        'jan': 1,
        'feb': 2,
        'mar': 3,
        'apr': 4,
        'may': 5,
        'jun': 6,
        'jul': 7,
        'aug': 8,
        'sep': 9,
        'oct': 10,
        'nov': 11,
        'dec': 12
    }
    s = string.strip()[:3].lower()

    try:
        out = m[s]
        return out
    except:
        raise ValueError('Not a month')


def month_num_to_str(intero):
    m = {
        1: 'Jan',
        2: 'Feb',
        3: 'Mar',
        4: 'Apr',
        5: 'May',
        6: 'Jun',
        7: 'Jul',
        8: 'Aug',
        9: 'Sep',
        10: 'Oct',
        11: 'Nov',
        12: 'Dec'
    }
    try:
        out = m[intero]
        return out
    except:
        raise ValueError('Not a month')


def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    init_db()
    print('Initialized the database')


def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route("/")
def type_cost():
    # GBP = gbp_on_euro()
    print("Converion made with ratio: " + str(GBP))
    error = None
    db = get_db()
    entries = list()
    for i in range(12):  # loop on the 12 months
        tot = 0  # money spent for each month
        if i + 1 < 10:  # need for query
            month = '0' + str(i + 1)
        else:
            month = str(i + 1)

        cur = db.execute(
            """SELECT amount, currency FROM entries
            WHERE strftime('%m', data) = '""" +
            month +
            """' and strftime('%Y', data) = '2016';""")  # only year 2016
        for row in cur.fetchall():
            if row[1] == 'e':  # if value added is euro, conversion
                tot = tot + round(row[0] * GBP, 1)
            else:
                tot = tot + row[0]

        entries.append({month_num_to_str(i + 1): round(tot, 1)})

    path1 = os.path.join(app.root_path, 'templates/categories.txt')
    print(path1)
    with app.open_resource(path1, mode='r') as f:
        data = f.readlines()

    return render_template('main.html', entries=entries,
                           error=error, cat=data,
                           mess='general',
                           change=GBP)


def checkdate(s):
    if re.search(r'2016\-[0-1][0-9]\-[0-3][0-9]', s) is None:
        return None
    num = s.split('-')
    if int(num[1]) < 12 and int(num[2]) < 31:
        return True
    else:
        return None


# add expenses in db and show total money spent each month of 2016
@app.route('/add', methods=['POST'])  # add expense in the db
def add_entry():
    if request.method == 'POST':
        print('POST')
        db = get_db()
        # simple controller on field and float type
        if (
            request.form['mydate'] == '' or
            request.form['categories'] == '' or
            request.form['item'] == ''
        ):
            flash("No empty fields!")
            return redirect(url_for('type_cost'))
        try:
            float(request.form['amount'])
        except ValueError:
            flash("Insert a valid amount, use '.' as separator!")
            return redirect(url_for('type_cost'))

        if checkdate(request.form['mydate']) is None:
            flash("Insert date as per requirements!")
            return redirect(url_for('type_cost'))

        db.execute("""insert into entries (data, category, item, amount, currency)
                      values (?, ?, ?, ?, ?)""",
                   [request.form['mydate'],
                       request.form['categories'],
                       request.form['item'],
                       request.form['amount'],
                       request.form['currency']])
        db.commit()
        flash('New expense was successfully added')
    return redirect(url_for('type_cost'))


# Display total money spent everyday + stat
@app.route('/month', methods=['POST'])  # show total for each month's day
def month():
    if request.method == 'POST':
        db = get_db()
        totals = list()
        mo = request.form['submit'].split('-')[0].strip()
        max_min = [0, 0, 0, 0, 0]  # max e min amount e relative days
        for j in range(monthrange(2016, month_string_to_number(mo))[1]):
            tot = 0
            m = month_string_to_number(mo)
            # adjust m e d for query success
            if m < 10:
                m = '0' + str(m)
            else:
                m = str(m)

            if j + 1 < 10:
                d = '0' + str(j + 1)
            else:
                d = str(j + 1)

            query = (
                """SELECT amount, currency FROM entries
                WHERE strftime('%m', data) = '""" +
                m +
                """' and strftime('%d', data) = '""" +
                d +
                """';""")
            cur = db.execute(query)
            if cur is None:
                tot = 0
            else:
                for row in cur.fetchall():  # total for each day
                    if row[1] == 'e':
                        tot = tot + round(row[0] * GBP, 1)
                    else:
                        tot = tot + row[0]

            totals.append(round(tot, 1))

        max_min[1] = max(totals)  # most expensive day
        max_min[0] = totals.index(max_min[1]) + 1  # most expensive day
        max_min[3] = min(totals)  # cheapest day
        max_min[2] = totals.index(max_min[3]) + 1  # cheapest day
        max_min[4] = datetime.datetime.today().day - datetime.datetime(2016,int(m),1).day
    return render_template(
        'main.html',
        mo=mo,
        mess='month',
        totals=totals,
        max_min=max_min,
        change = GBP)


# Display expense details for the selected day
@app.route('/days', methods=['POST'])
def days():
    if request.method == 'POST':
        m = month_string_to_number(request.form['month'])
        if m < 10:
            mo = '0' + str(m)
        else:
            mo = str(m)

        try:
            d = int(request.form['submit'][:2])
            dy = str(d)
        except ValueError:
            d = int(request.form['submit'][0])
            dy = '0' + str(d)

        query = (
            """SELECT id, category, item, amount, currency FROM entries
            WHERE strftime('%m', data) = '""" +
            mo +
            """' and strftime('%d', data) = '""" +
            dy +
            """';""")
        db = get_db()
        cur = db.execute(query)

    return render_template(
        'days.html',
        entries=cur.fetchall(),
        m=request.form['month'],
        dy=d)

if __name__ == '__main__':
    app.run(debug=True)

