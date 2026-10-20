"""The screening rules, measured against the submissions Robotist actually received.

The fixtures are real rows copied out of the inquiries table (September to October 2026),
with their field values shortened but not altered. Two properties matter, and they are not
symmetrical: every genuine inquiry that reached the team must keep reaching it, and the
form-spam that filled the console must stop e-mailing the team.
"""

from grn.screening import screen

# Submissions from real customers. Holding one of these back is a lost lead.
GENUINE = [
    # RQ-7D48B8DE55 — our own delivery check
    {'name': 'Email delivery check (please ignore)', 'email': 'lareesa@robotist.com.au', 'company': 'Robotist internal', 'interest': 'Delivery verification', 'message': 'Internal delivery check for the new notification mail on the website backend. Please ignore this row.'},
    # RQ-B8349BB89C — our own test submission
    {'name': 'Lareesa Hu', 'email': 'lareesa@pulse-branding.com', 'company': 'Pulse Branding', 'interest': '', 'message': 'Testing testing'},
    # RQ-C9E3FBE038 — Mike Powrie, asks about a cleaning robot
    {'name': 'Mike powrie', 'email': 'michael.powrie@neonnow.ai', 'company': 'Neonnow', 'interest': 'rental', 'message': 'Robot for home cleaning, washing, folding laundry duties'},
    # RQ-47B2B67FA8 — Sadhana, wants to try the Panther
    {'name': 'Sadhana', 'email': 'hsdesai@gmail.com', 'company': 'desai pty', 'interest': 'rental', 'message': 'I would like to try out the Panther model for household use on 2 levels with a lift. I am open to renting or buying as long as it is cost effective an…'},
    # RQ-6540BC116B — dennis xie, general robot question
    {'name': 'dennis xie', 'email': 'dennis@prmu.com', 'company': 'prmu', 'interest': 'other', 'message': 'just general robot'},
    # RQ-2B303FF24B — our own test submission
    {'name': 'Lareesa Hu', 'email': 'lareesa@pulse-branding.com', 'company': 'Pulse Branding', 'interest': '', 'message': 'Test test'},
]

# Form spam: prize-scam links, SEO pitches, and the machine-generated "what is your price"
# bots in a dozen languages. Each one names the rule that must catch it.
HELD = [
    # link-in-message
    ({'name': 'Richardwew', 'email': 'zurichjamespacana@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'Read the news and achieve $50,000,000 per month consistently https://telegra.ph/Read-the-latest-news-and-earn-50000000-i…'}, 'link-in-message'),
    # generated-name
    ({'name': 'RobertOvamb', 'email': 'joshuaguerrero2v7t40d@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'Hi, kam dashur të di çmimin tuaj'}, 'generated-name'),
    # keyword:seo
    ({'name': 'Prakash Singh', 'email': 'donohoe.sabrina42@gmail.com', 'company': 'Sabrina Donohoe', 'interest': 'cleaning', 'message': 'Hello, Are you losing your business to competitors? Rank on the first page of Google to get maximum organic traffic and …'}, 'keyword:'),
    # link-in-message
    ({'name': 'Robertdrore', 'email': 'Peanut.101.jm@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'The 2026 Rolls-Royce Phantom for $15,000 Is Finally Within Reach https://telegra.ph/How-to-get-a-new-2026-Rolls-Royce-Ph…'}, 'link-in-message'),
    # gibberish
    ({'name': 'RobertOvamb', 'email': 'gregoryj8tl2g@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'হাই, আমি আপনার মূল্য জানতে চেয়েছিলাম.'}, 'gibberish'),
    # generated-name
    ({'name': 'RobertOvamb', 'email': 'gregoryj8tl2g@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'Ndewo, achọrọ m ịmara ọnụahịa gị.'}, 'generated-name'),
    # keyword:seo
    ({'name': 'Neeraj Madhukar', 'email': 'neerajmadhu3654@outlook.com', 'company': 'Ethel Callanan', 'interest': 'humanoid', 'message': "Hi, Hope you're doing well! We are a top digital marketing agency offering SEO, SMO, PPC, and SMM services to boost your…"}, 'keyword:'),
    # generated-name
    ({'name': 'RobertOvamb', 'email': 'hsilojhonaisy@gmail.com', 'company': 'google', 'interest': 'other', 'message': 'Hola, volia saber el seu preu.'}, 'generated-name'),
]



def test_real_customers_are_never_held_back():
    for row in GENUINE:
        assert screen(row) == '', row['name'] + ' would not have been notified'


def test_form_spam_is_held_back_with_a_readable_reason():
    for row, expected in HELD:
        reason = screen(row)
        assert reason, 'spam would have e-mailed the team: ' + row['name']
        assert expected in reason, (row['name'], reason)


def test_one_weak_signal_is_not_enough():
    """A generated-looking name on its own must not cost a real inquiry."""
    assert screen({'name': 'RobertOvamb', 'email': 'robert@example.com', 'company': 'Acme Robotics',
                   'interest': 'rental', 'message': 'We would like a quote for two units for our warehouse.'}) == ''


def test_a_link_somewhere_in_a_short_message_is_decisive():
    assert screen({'name': 'Jane Doe', 'email': 'jane@example.com', 'company': 'Acme',
                   'interest': 'purchase', 'message': 'See https://telegra.ph/prize-claim'}) == 'link-in-message'


def test_one_link_inside_a_long_genuine_message_is_still_notified():
    message = ('Hello, we run a hotel in Sydney and would like pricing for a reception robot. '
               'Our site is https://example.com and the floor plan is on it. We would also like to '
               'know about service cover, spare parts, training for our staff, delivery time, and '
               'whether a twelve month rental includes maintenance. Our lobby is open from six in '
               'the morning until eleven at night, seven days a week, and the robot would greet '
               'guests and answer simple questions at the desk. Please send a quotation when you can. ')
    assert len(message) > 400
    assert screen({'name': 'Anna Lee', 'email': 'anna@example.com', 'company': 'Harbour Hotel',
                   'interest': 'rental', 'message': message}) == ''
