<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>회원정보 저장</title>
<link rel="stylesheet" type="text/css" href="../css/member.css">
</head>
<body>
<%
request.setCharacterEncoding("UTF-8");
String[] hobby=request.getParameterValues("hobby");

String texthobby="";

for(int i=0;i<hobby.length;i++){
	texthobby+=hobby[i] + " ";
}

%>

<!-- 클래스: MemberDTO 객체이름: mbean -->
<jsp:useBean class="model.MemberDTO" id="mbean">
		<jsp:setProperty name="mbean" property="*"/> <!-- property=getset이용  setProperty 다붙음-->
</jsp:useBean>

<jsp:useBean class="model.MemberDAO"  id="mdao" />

<%
//회원가입
mbean.setHobby(texthobby);
mdao.insertMember(mbean);
//회원목록 출력
response.sendRedirect("MemberList.jsp");
%>

회원가입 완료!!
	
</body>
</html>