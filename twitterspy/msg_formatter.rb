module TwitterSpy

  module MsgFormatter

    def user_link(user)
      linktext=user
      if user[0] == 64 # Does it start with @?
        user = user.gsub(/^@(.*)/, '\1')
      end
      %Q{<a href="http://twitter.com/#{user}">#{linktext}</a>}
    end

    def type_str(type)
      type.nil? ? '' : "#{type} "
    end

    def format_html_body(from, text, type)
      user = user_link(from)
      text = text.gsub(/(\W*)(@[\w_]+)/) {|x| $1 + user_link($2)}.gsub(/&/, '&amp;')
      "#{type_str(type)}#{user}: #{text}"
    end

    def format_plain_body(from, text, type)
      "#{type_str(type)}#{from}: #{text}"
    end

    def format_msg(jid, from, text, subject="Track Message", type=nil)
      body = format_plain_body(from, text, type)
      m = Jabber::Message::new(jid, body).set_type(:chat).set_id('1').set_subject(subject)

      # The html itself
      html = format_html_body(from, text, type)
      begin
        REXML::Document.new "<html>#{html}</html>"

        h = REXML::Element::new("html")
        h.add_namespace('http://jabber.org/protocol/xhtml-im')

        # The body part with the correct namespace
        b = REXML::Element::new("body")
        b.add_namespace('http://www.w3.org/1999/xhtml')

        t = REXML::Text.new(html, false, nil, true, nil, %r/.^/ )

        b.add t
        h.add b
        m.add_element(h)
      rescue REXML::ParseException
        puts "Nearly made bad html:  #{$!} (#{text})"
        $stdout.flush
      end

      m
    end
  end

end