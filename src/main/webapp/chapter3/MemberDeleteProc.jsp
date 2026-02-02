<%@page import="model.MemberDAO"%>
<%@page import="model.MemberDTO"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Del Proc</title>
</head>
<body>
<%
    request.setCharacterEncoding("UTF-8");
%>

<jsp:useBean class="model.MemberDTO" id="mdto" />
<jsp:setProperty name="mdto" property="*" />

<%
MemberDAO mdao = new MemberDAO();
String dbPass = mdao.getPass(mdto.getId());

// dbPass가 null이면: 그런 id가 없거나 조회 실패
if (dbPass != null && dbPass.equals(mdto.getPass1())) {
    mdao.deleteMember(mdto.getId());   // ✅ id로 삭제
    response.sendRedirect("MemberList.jsp");
} else {
%>
<script type="text/javascript">
    alert("패스워드가 일치하지 않습니다.");
    history.go(-1);
</script>
<%
}
%>

</body>
</html>