from rhino.vendor import mimeparse

def test_mimeparse_q0():
    """Test for a bug in the official mimeparse release that is fixed in our
    vendored version."""
    assert mimeparse.parse_media_range('image/*; q=0.0') == ('image', '*', {'q': '0.0'})
