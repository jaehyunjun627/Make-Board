<%@ page language="java" contentType="text/html; charset=UTF-8"
   pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core"%>
<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>choose</title>
</head>
<body bgcolor="#FFFFcc">

   <h3>&lt;c:choose&gt;</h3>
   <form>
      <select name="sel">
         <option>--</option>
         <option ${param.sel == 'a'? 'selected':'' }>a</option>
         <option ${param.sel == 'b'? 'selected':'' }>b</option>
         <option ${param.sel == 'c'? 'selected':'' }>c</option>
         <option ${param.sel == 'd'? 'selected':'' }>d</option>
      </select>
      <input type="submit" value="선택" />
   </form>
   <p></p>
   <hr />
   <c:choose>
      <c:when test="${param.sel == 'a' }">a 선택됨</c:when>
      <c:when test="${param.sel == 'b' }">b 선택됨</c:when>
      <c:when test="${param.sel == 'c' }">c 선택됨</c:when>
      <c:when test="${param.sel == 'd' }">d 선택됨</c:when>
      <c:otherwise>a,b,c,d 이외의 것을 선택함</c:otherwise>
   </c:choose>
   
   

</body>
</html>