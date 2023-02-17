![](/../imgs/demo.png)

This script polls the Gencon housing website looking for hotel rooms near the ICC, and alerts you in a variety of ways when available rooms are found. It requires a relatively modern version of [Python](https://www.python.org/) 2 (2.7.9+) or 3.

This was most recently updated for Gencon 2023. If it's currently a later year, I'll probably be putting out an update soon after housing opens. If that doesn't happen, you can probably figure out [what to edit](https://github.com/mrozekma/gencon-hotel-check/blob/master/gencon-hotel-check.py#L30-L31) to get it working assuming nothing major has changed on the housing website.

## Output

The columns in the script's output are:

* `Distance` -- How far away the hotel is. By default only rooms in the "blocks" range are shown, as these are the only rooms the script will ever care alert you about, but `--show-all` will also show the hotels miles away. "Skywalk" means the hotel is connected to the ICC by a skywalk.
* `Price` -- The total price, before taxes/fees. Essentially the nightly rate times the number of nights.
* `Hotel` -- The name of the hotel.
* `Room` -- The description of the room. If the hotel has multiple rooms, there will be multiple lines in the output. The number in parentheses is how many rooms with that description are available.

## Usage

To fetch and run the script, open a terminal (Linux, Mac) / command prompt (Windows) and run:

```sh
git clone https://github.com/mrozekma/gencon-hotel-check.git
cd gencon-hotel-check
python gencon-hotel-check.py
```

If you don't have git, you can open the [raw file](https://raw.githubusercontent.com/mrozekma/gencon-hotel-check/master/gencon-hotel-check.py) on Github and save it.

Before you can use the script, you need to get a URL from the housing website.

* Go to https://www.gencon.com/housing.
* Click "Go to Housing Portal" or "Manage Room", depending on if you already have a room.
* You should end up on a page with a URL like https://book.passkey.com/entry?token=...

`gencon-hotel-check.py --help` outputs the complete list of arguments, but these are the most important:

* `--url` is the only mandatory argument. Pass the URL you ended up on above (`--url "https://book.passkey.com/entry?token=..."`). The URL might contain special characters (e.g. `&`), so be sure to put quotes around it.
* `--checkin` and `--checkout` specify the date range you need. The default is the days of the convention, Thursday through Sunday. Since Wednesday through Sunday is also very common, you can use `--wednesday` as a shorthand.

**NOTE**: I recommend that after setting things up the first time, including the miscellaneous alerts, you try one run including the `--test` flag. This will trigger all the alerts you've requested with some test data, to make sure they're working correctly. I make no guarantees that they'll work when a real hotel room is found, but checking that they're right ahead of time can't hurt. Speaking of which:

## Alerts

Once a hotel is found, the script needs to alert you in some way. It will output the matching hotel(s) with exclamation points next to them, but unless you're looking at the terminal at the time that probably won't help. You can specify any combination of the following options, multiple times each if necessary (e.g. to e-mail multiple people).

### Show popup

![](/../imgs/alert-popup.png)

`gencon-hotel-check.py --popup`

Popup a dialog box. On Windows this will use the win32 api if possible (via the [pypiwin32 package](https://pypi.python.org/pypi/pypiwin32/)). If not, or on other platforms, it uses Tkinter, which is typically built into Python.

### Run command

`gencon-hotel-check.py --cmd CMD`

Run the specified command, passing each hotel as a separate argument. This is probably most useful on Linux. For example, passing the path to this script will result in a libnotify popup:

```sh
#!/bin/bash
lines="$1"
shift
for i in "$@"; do
	lines="$lines\n$i"
done
notify-send -u critical "Gencon Hotel Alert" "$lines"
```

![](/../imgs/alert-libnotify.png)

### Open browser

`gencon-hotel-check.py --browser`

Open the housing site in the system's default browser. There's no simple way to open the search results directly, so it will send you to the first page of the housing search wizard.

### Send e-mail

`gencon-hotel-check.py --email SMTP_HOST FROM_ADDRESS TO_ADDRESS`

Send an e-mail that lists the found hotels and includes a link to the housing site. Most SMTP servers are authenticated, so you need to give a from address that has permission to send via specified SMTP server, and give the corresponding password when running the script. If you have an unauthenticated SMTP server available, you can use that instead and leave the password blank when the script asks. The script has been tested with Gmail, so I can confirm that if nothing else, it works there (host is `smtp.gmail.com`).

### Send Pushbullet

`gencon-hotel-check.py --pushbullet ACCESS_TOKEN`

Send an alert to all of your devices via [Pushbullet](https://www.pushbullet.com/). This requires a free Pushbullet account, and an API access token that can be generated [here](https://www.pushbullet.com/#settings).

### SMS

SMS messaging is not directly supported, as it generally requires access to a paid API. However, most carriers provide a [gateway](https://en.wikipedia.org/wiki/SMS_gateway#Email_clients) that can be used to send SMS messages via e-mail. This is the main reason the e-mail alert option provides a distinct "to" address -- it's expected that you'll be sending the e-mail to yourself (i.e. to the "from" address), but you can also send it to your phone via an SMS gateway.

## Filtering

By default, the script looks for hotels near the ICC (where "near" means the distance is measure in "blocks", not "miles") that have rooms available in the date range you specified. There are a variety of optional arguments to narrow this down further if necessary:

* `--max-distance` specifies the maximum blocks away the hotel can be. If 4 blocks is the farthest you want to walk, use `--max-distance 4`. If you require a hotel connected to the ICC by a skywalk, use `--max-distance connected` (or just `--connected`).
* `--budget` specifies the max amount you're willing to pay. This is the sum of all the days (not just the daily rate), but does not include taxes or other fees. This means if there's a $200/night room available Wednesday-Sunday, you need a max budget of at least $800 to see it.
* `--hotel-regex` and `--room-regex` are [regular expressions](https://en.wikipedia.org/wiki/Regular_expression) compared (case-insensitively) against the hotel name and room description. Explaining regular expressions would take a while, but here are some likely common cases:
  - To require that a particular value show up somewhere, just specify that value. To only show Marriott hotels: `--hotel-regex "marriott"`
  - To require one of a set of values show up, separate them with `|`. To only show hotels with double or queen beds: `--room-regex "double|queen"`
